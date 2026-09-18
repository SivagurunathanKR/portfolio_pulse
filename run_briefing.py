import asyncio
import os
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select

from app.models import Holding, MutualFund
from app.services.analytics import compute_portfolio_metrics
from app.services.ai_advisor import generate_portfolio_briefing, send_telegram_alert

load_dotenv()

async def main():
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("[Error]: DATABASE_URL is missing.")
        return

    print("Connecting to Neon database...")
    engine = create_async_engine(database_url, echo=False)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        query = select(Holding, MutualFund).join(
            MutualFund, Holding.scheme_code == MutualFund.scheme_code
        )
        result = await db.execute(query)
        rows = result.all()

        if not rows:
            print("[Error]: No holdings found in database.")
            return

        raw_holdings = [
            {
                "scheme_code": holding.scheme_code,
                "scheme_name": fund.scheme_name,
                "total_units": float(holding.total_units),
                "invested_amount": float(holding.invested_amount),
                "average_nav": float(holding.average_nav) if holding.average_nav else 0.0
            }
            for holding, fund in rows
        ]

    print(f"Loaded {len(raw_holdings)} holdings. Computing live metrics...")
    
    # Calculates Valuation, Daily P&L, and Total P&L via live AMFI NAVs
    metrics = await compute_portfolio_metrics(raw_holdings)
    ai_insights = await generate_portfolio_briefing(metrics)

    daily_sign = "+" if metrics.get('daily_pnl', 0) >= 0 else ""
    total_sign = "+" if metrics.get('total_pnl', 0) >= 0 else ""

    # ---- FUND-WISE BREAKDOWN ----
    funds_text = "<b>🏦 Fund-wise Breakdown:</b>\n"
    for fund in metrics.get("funds", []):
        name = fund.get("scheme_name", "Unknown")
        short_name = (name[:27] + '...') if len(name) > 30 else name 
        
        current = fund.get("current_value", 0)
        daily = fund.get("daily_pnl", 0)
        total = fund.get("total_pnl", 0)
        
        daily_icon = "🟩" if daily >= 0 else "🟥"
        total_icon = "🟢" if total >= 0 else "🔴"
        daily_sign_fund = "+" if daily >= 0 else ""
        total_sign_fund = "+" if total >= 0 else ""

        funds_text += (
            f"🔹 <b>{short_name}</b>\n"
            f"   Val: ₹{current:,.2f} | 1D: {daily_icon} {daily_sign_fund}₹{abs(daily):,.2f} | Tot: {total_icon} {total_sign_fund}₹{abs(total):,.2f}\n"
        )
    # -----------------------------

    alert_text = (
        f"📊 <b>PortfolioPulse Daily Briefing</b>\n"
        f"📅 <b>NAV Date:</b> {metrics.get('as_of_date', 'N/A')}\n\n"
        f"• <b>Total Invested:</b> ₹{metrics['total_invested']:,.2f}\n"
        f"• <b>Current Value:</b> ₹{metrics['current_value']:,.2f}\n"
        f"• <b>Today's P&L:</b> {daily_sign}₹{metrics.get('daily_pnl', 0):,.2f} ({daily_sign}{metrics.get('daily_percentage', 0):.2f}%)\n"
        f"• <b>Total P&L:</b> {total_sign}₹{metrics['total_pnl']:,.2f} ({total_sign}{metrics['percentage_return']:.2f}%)\n\n"
        f"{funds_text}\n"
        f"💡 <b>AI Market Insights:</b>\n{ai_insights}"
    )

    await send_telegram_alert(alert_text)
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())