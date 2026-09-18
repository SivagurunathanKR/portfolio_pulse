import os
import httpx
from datetime import datetime
from typing import List, Dict, Any
from dotenv import load_dotenv

load_dotenv()

AMFI_PORTAL_URL = os.getenv(
    "AMFI_PORTAL_URL", 
    "https://portal.amfiindia.com/spages/NAVAll.txt"
)

async def fetch_amfi_master_feed() -> Dict[str, Dict[str, Any]]:
    """
    Downloads AMFI's official NAV master text file in a single request
    and indexes every scheme code into a fast memory dictionary.
    """
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
                    # AMFI format: Scheme Code;ISIN Div;ISIN Growth;ISIN Reinv;Scheme Name;NAV;Date
                    # Date is always the last item, NAV is the second to last numeric item
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

async def compute_portfolio_metrics(holdings: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Calculates total portfolio valuation, 1-day P&L, and overall returns
    directly against AMFI official live records.
    """
    amfi_catalog = await fetch_amfi_master_feed()

    total_invested = 0.0
    current_value = 0.0
    daily_pnl = 0.0
    funds_breakdown = []
    valid_dates = []

    for h in holdings:
        # Normalize code to stripped string
        code = str(h["scheme_code"]).strip()
        units = float(h["total_units"])
        avg_nav = float(h["average_nav"])
        invested = float(h.get("invested_amount") or (units * avg_nav))

        # Lookup in catalog with fallback
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

        # Baseline previous nav for 1-day telemetry
        p_nav = float(h.get("previous_nav") or avg_nav)
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

    # Resolve dates
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