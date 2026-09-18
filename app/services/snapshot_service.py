from typing import List, Dict
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.models import NAVHistory
from app.services.nav_fetcher import fetch_nav_by_scheme_code
from app.database import async_session_maker

async def record_daily_snapshots_task(scheme_codes: List[str]):
    """
    Background worker function that runs independently of the HTTP response.
    Fetches live NAVs and idempotently inserts them into nav_history.
    """
    async with async_session_maker() as db:
        for code in scheme_codes:
            nav_data = await fetch_nav_by_scheme_code(code)
            if not nav_data:
                continue

            date_str = nav_data["date"]
            nav_val = nav_data["nav"]

            # Idempotency Check: Don't insert duplicate records for the same day
            stmt = select(NAVHistory).where(
                and_(
                    NAVHistory.scheme_code == code,
                    NAVHistory.nav_date == date_str
                )
            )
            existing = (await db.execute(stmt)).scalar_one_or_none()

            if not existing:
                snapshot = NAVHistory(
                    scheme_code=code,
                    nav_date=date_str,
                    nav_value=nav_val
                )
                db.add(snapshot)

        await db.commit()