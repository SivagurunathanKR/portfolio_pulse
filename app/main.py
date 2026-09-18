from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from contextlib import asynccontextmanager
from pydantic import BaseModel, Field
from fastapi import BackgroundTasks

from app.services.ai_advisor import generate_portfolio_briefing, send_telegram_alert
from app.services.snapshot_service import record_daily_snapshots_task
from app.services.analytics import compute_portfolio_metrics
from app.database import engine, Base, get_db
from app.models import MutualFund, Holding, NAVHistory
from app.services.nav_fetcher import fetch_nav_by_scheme_code

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensures tables exist in Neon PostgreSQL on startup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    # Disposes the connection pool cleanly on shutdown
    await engine.dispose()

app = FastAPI(
    title="PortfolioPulse API",
    description="Autonomous Mutual Fund Tracker & Cloud DB",
    version="0.2.0",
    lifespan=lifespan
)

# Pydantic Schema for adding a holding
class HoldingCreate(BaseModel):
    scheme_code: str = Field(..., example="135762")
    total_units: float = Field(..., gt=0, example=150.25)
    average_nav: float = Field(..., gt=0, example=24.50)

@app.get("/")
async def root():
    return {"status": "online", "message": "PortfolioPulse API connected to Neon PostgreSQL!"}

@app.get("/api/v1/nav/{scheme_code}")
async def get_fund_nav(scheme_code: str):
    """
    Live lookup from AMFI text registry
    """
    result = await fetch_nav_by_scheme_code(scheme_code)
    if not result:
        raise HTTPException(
            status_code=404, 
            detail=f"Scheme code {scheme_code} not found in AMFI records"
        )
    return {"status": "success", "data": result}

@app.post("/api/v1/holdings")
async def add_or_update_holding(
    payload: HoldingCreate, 
    db: AsyncSession = Depends(get_db)
):
    """
    1. Fetches official scheme details from AMFI
    2. Registers the fund in `mutual_funds` table if absent
    3. Saves unit balance and investment cost into `holdings`
    """
    # 1. Verify scheme code against live AMFI registry
    amfi_data = await fetch_nav_by_scheme_code(payload.scheme_code)
    if not amfi_data:
        raise HTTPException(
            status_code=400, 
            detail="Invalid scheme code: Not registered with AMFI"
        )

    # 2. Check or insert into mutual_funds table
    query_fund = select(MutualFund).where(MutualFund.scheme_code == payload.scheme_code)
    result = await db.execute(query_fund)
    fund = result.scalar_one_or_none()

    if not fund:
        fund = MutualFund(
            scheme_code=payload.scheme_code,
            scheme_name=amfi_data["scheme_name"]
        )
        db.add(fund)
        await db.flush()

    # 3. Insert or update holding
    query_holding = select(Holding).where(Holding.scheme_code == payload.scheme_code)
    result_holding = await db.execute(query_holding)
    holding = result_holding.scalar_one_or_none()

    invested_total = round(payload.total_units * payload.average_nav, 2)

    if holding:
        holding.total_units = payload.total_units
        holding.average_nav = payload.average_nav
        holding.invested_amount = invested_total
    else:
        holding = Holding(
            scheme_code=payload.scheme_code,
            total_units=payload.total_units,
            average_nav=payload.average_nav,
            invested_amount=invested_total
        )
        db.add(holding)

    await db.commit()
    await db.refresh(holding)

    return {
        "status": "success",
        "message": "Holding registered successfully",
        "data": {
            "scheme_code": holding.scheme_code,
            "scheme_name": fund.scheme_name,
            "total_units": holding.total_units,
            "invested_amount": holding.invested_amount
        }
    }

@app.get("/api/v1/holdings")
async def list_holdings(db: AsyncSession = Depends(get_db)):
    """
    Retrieves all registered holdings from Neon DB
    """
    query = select(Holding, MutualFund).join(
        MutualFund, Holding.scheme_code == MutualFund.scheme_code
    )
    results = await db.execute(query)
    rows = results.all()

    portfolio = []
    for holding, fund in rows:
        portfolio.append({
            "scheme_code": holding.scheme_code,
            "scheme_name": fund.scheme_name,
            "total_units": holding.total_units,
            "average_nav": holding.average_nav,
            "invested_amount": holding.invested_amount
        })

    return {"status": "success", "count": len(portfolio), "portfolio": portfolio}

@app.get("/api/v1/portfolio/analytics")
async def get_portfolio_analytics(db: AsyncSession = Depends(get_db)):
    """
    Computes real-time P&L and portfolio value by joining 
    stored holdings with live AMFI market rates.
    """
    # 1. Fetch persistent holdings with joined scheme names
    query = select(Holding, MutualFund).join(
        MutualFund, Holding.scheme_code == MutualFund.scheme_code
    )
    result = await db.execute(query)
    rows = result.all()

    # 2. Format holdings for the analytics engine
    raw_holdings = [
        {
            "scheme_code": holding.scheme_code,
            "scheme_name": fund.scheme_name,
            "total_units": holding.total_units,
            "average_nav": holding.average_nav,
            "invested_amount": holding.invested_amount
        }
        for holding, fund in rows
    ]

    # 3. Compute real-time analytics
    metrics = await compute_portfolio_metrics(raw_holdings)

    return {
        "status": "success",
        "data": metrics
    }

@app.post("/api/v1/portfolio/snapshot")
async def trigger_portfolio_snapshot(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """
    Dispatches an asynchronous background task to record today's NAV 
    for all registered mutual funds into the nav_history table.
    """
    # 1. Retrieve all registered scheme codes
    result = await db.execute(select(MutualFund.scheme_code))
    scheme_codes = result.scalars().all()

    if not scheme_codes:
        raise HTTPException(
            status_code=400,
            detail="No mutual funds registered in database to snapshot."
        )

    # 2. Push job to FastAPI native background runner
    background_tasks.add_task(record_daily_snapshots_task, list(scheme_codes))

    return {
        "status": "accepted",
        "message": f"Snapshot triggered in background for {len(scheme_codes)} fund(s)."
    }

@app.get("/api/v1/portfolio/history/{scheme_code}")
async def get_scheme_history(
    scheme_code: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieves all historic daily snapshots recorded for a specific scheme.
    """
    query = (
        select(NAVHistory)
        .where(NAVHistory.scheme_code == scheme_code)
        .order_by(NAVHistory.id.desc())
    )
    result = await db.execute(query)
    snapshots = result.scalars().all()

    if not snapshots:
        raise HTTPException(
            status_code=404,
            detail=f"No historic snapshots found for scheme code {scheme_code}."
        )

    return {
        "status": "success",
        "scheme_code": scheme_code,
        "count": len(snapshots),
        "history": [
            {
                "id": row.id,
                "nav_date": row.nav_date,
                "nav_value": row.nav_value
            }
            for row in snapshots
        ]
    }

@app.post("/api/v1/portfolio/notify")
async def trigger_ai_portfolio_briefing(
    send_telegram: bool = True,
    db: AsyncSession = Depends(get_db)
):
    """
    1. Computes live valuation metrics across all holdings (including 1-day daily P&L).
    2. Uses Groq LLM to generate an objective financial briefing.
    3. Dispatches formatted HTML alert to Telegram.
    """
    # 1. Fetch holdings with fund metadata
    query = select(Holding, MutualFund).join(
        MutualFund, Holding.scheme_code == MutualFund.scheme_code
    )
    rows = (await db.execute(query)).all()

    if not rows:
        raise HTTPException(status_code=400, detail="No holdings to analyze.")

    raw_holdings = [
        {
            "scheme_code": holding.scheme_code,
            "scheme_name": fund.scheme_name,
            "total_units": holding.total_units,
            "average_nav": holding.average_nav,
            "invested_amount": holding.invested_amount
        }
        for holding, fund in rows
    ]

    # 2. Compute valuation & 1-day metrics
    metrics = await compute_portfolio_metrics(raw_holdings)

    # 3. Generate AI summary
    ai_insights = await generate_portfolio_briefing(metrics)

    # 4. Format Telegram notification with HTML & signs
    daily_sign = "+" if metrics.get('daily_pnl', 0) >= 0 else ""
    total_sign = "+" if metrics.get('total_pnl', 0) >= 0 else ""

    alert_text = (
        f"📊 <b>PortfolioPulse Daily Briefing</b>\n"
        f"📅 <b>NAV Date:</b> {metrics.get('as_of_date', 'N/A')}\n\n"
        f"• <b>Total Invested:</b> ₹{metrics['total_invested']:,.2f}\n"
        f"• <b>Current Value:</b> ₹{metrics['current_value']:,.2f}\n"
        f"• <b>Today's P&L:</b> {daily_sign}₹{metrics.get('daily_pnl', 0):,.2f} ({daily_sign}{metrics.get('daily_percentage', 0):.2f}%)\n"
        f"• <b>Total P&L:</b> {total_sign}₹{metrics['total_pnl']:,.2f} ({total_sign}{metrics['percentage_return']:.2f}%)\n\n"
        f"💡 <b>AI Market Insights:</b>\n{ai_insights}"
    )

    telegram_delivered = False
    if send_telegram:
        telegram_delivered = await send_telegram_alert(alert_text)

    return {
        "status": "success",
        "metrics": metrics,
        "ai_briefing": ai_insights,
        "telegram_notified": telegram_delivered
    }