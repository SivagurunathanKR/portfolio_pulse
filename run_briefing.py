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
        print("[Error]: DATABASE_URL environment variable is missing.")
        return

    print("Connecting to Neon database...")
    engine = create_async_engine(database_url, echo=False)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        # 1. Fetch holdings with fund metadata
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
                "total_units": holding.total_units,
                "average_nav": holding.average_nav,
                "invested_amount": holding.invested_amount
            }
            for holding, fund in rows
        ]

    print(f"Loaded {len(raw_holdings)} holdings. Computing metrics...")
    
    # 2. Compute valuation & live NAVs from AMFI
    metrics = await compute_portfolio_metrics(raw_holdings)

    print("Generating AI market insights via Groq...")
    # 3. Generate AI summary
    ai_insights = await generate_portfolio_briefing(metrics)

    # 4. Format Telegram notification
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

    print("Sending Telegram notification...")
    success = await send_telegram_alert(alert_text)
    if success:
        print("Telegram briefing dispatched successfully!")
    else:
        print("[Error]: Failed to deliver Telegram alert.")

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())