import os
import httpx
from datetime import datetime
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

load_dotenv()

AMFI_PORTAL_URL = os.getenv(
    "AMFI_PORTAL_URL", 
    "https://portal.amfiindia.com/spages/NAVAll.txt"
)

async def fetch_amfi_master_feed() -> Dict[str, Dict[str, Any]]:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/plain,text/html,application/xhtml+xml"
    }
    nav_catalog: Dict[str, Dict[str, Any]] = {}

    async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
        try:
            response = await client.get(AMFI_PORTAL_URL, headers=headers)
            if response.status_code == 200:
                for line in response.text.splitlines():
                    line = line.strip()
                    if not line or ";" not in line:
                        continue
                    
                    parts = line.split(";")
                    if len(parts) >= 5:
                        code = parts[0].strip()
                        date_str = parts[-1].strip()
                        nav_str = parts[-2].strip()

                        try:
                            nav_val = float(nav_str)
                            nav_catalog[code] = {
                                "current_nav": nav_val,
                                "date": date_str
                            }
                        except ValueError:
                            continue
        except Exception as e:
            print(f"[AMFI Master Feed Error]: {e}")

    return nav_catalog

async def fetch_previous_nav(scheme_code: str) -> Optional[float]:
    """Fetches historical NAV data to calculate accurate 1-day P&L."""
    url = f"https://api.mfapi.in/mf/{scheme_code}"
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(url)
            if resp.status_code == 200:
                data = resp.json().get("data", [])
                if len(data) >= 2:
                    # data[0] is the latest NAV, data[1] is the previous day's NAV
                    return float(data[1]["nav"])
        except Exception as e:
            print(f"[MFAPI Error] Failed to fetch history for {scheme_code}: {e}")
    return None

async def compute_portfolio_metrics(holdings: List[Dict[str, Any]]) -> Dict[str, Any]:
    amfi_catalog = await fetch_amfi_master_feed()

    total_invested = 0.0
    current_value = 0.0
    daily_pnl = 0.0
    funds_breakdown = []
    valid_dates = []

    for h in holdings:
        code = str(h["scheme_code"]).strip()
        units = float(h["total_units"])
        avg_nav = float(h["average_nav"])
        invested = float(h.get("invested_amount") or (units * avg_nav))

        live_data = amfi_catalog.get(code)
        if live_data:
            c_nav = live_data["current_nav"]
            nav_date = live_data["date"]
            valid_dates.append(nav_date)
        else:
            c_nav = avg_nav
            nav_date = "N/A"

        c_val = round(units * c_nav, 2)
        fund_total_pnl = round(c_val - invested, 2)

        # FIX: Fetch the exact previous day's NAV for accurate Daily P&L
        fetched_p_nav = await fetch_previous_nav(code)
        p_nav = fetched_p_nav if fetched_p_nav else avg_nav
        
        fund_daily_pnl = round(units * (c_nav - p_nav), 2)

        total_invested += invested
        current_value += c_val
        daily_pnl += fund_daily_pnl

        funds_breakdown.append({
            "scheme_code": code,
            "scheme_name": h.get("scheme_name", code),
            "invested_amount": round(invested, 2),
            "current_value": c_val,
            "total_pnl": fund_total_pnl,
            "daily_pnl": fund_daily_pnl,
            "nav": c_nav,
            "date": nav_date
        })

    if valid_dates:
        unique_dates = list(set(valid_dates))
        try:
            sorted_dates = sorted(
                unique_dates,
                key=lambda d: datetime.strptime(d, "%d-%b-%Y")
            )
            if len(sorted_dates) > 1:
                latest_date = f"{sorted_dates[-1]} ({sorted_dates[0]} for intl/delayed)"
            else:
                latest_date = sorted_dates[0]
        except Exception:
            latest_date = unique_dates[0]
    else:
        latest_date = "N/A"

    total_pnl = round(current_value - total_invested, 2)
    percentage_return = round((total_pnl / total_invested) * 100, 2) if total_invested > 0 else 0.0
    daily_percentage = round((daily_pnl / (current_value - daily_pnl)) * 100, 2) if (current_value - daily_pnl) > 0 else 0.0

    return {
        "as_of_date": latest_date,
        "total_invested": round(total_invested, 2),
        "current_value": round(current_value, 2),
        "total_pnl": total_pnl,
        "percentage_return": percentage_return,
        "daily_pnl": round(daily_pnl, 2),
        "daily_percentage": daily_percentage,
        "funds": funds_breakdown
    }