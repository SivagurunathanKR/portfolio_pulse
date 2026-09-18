import httpx
from typing import Dict, Optional

AMFI_URL = "https://www.amfiindia.com/spages/NAVAll.txt"

async def fetch_nav_by_scheme_code(scheme_code: str) -> Optional[Dict]:
    """
    Downloads the daily AMFI text data and parses it line-by-line
    to find a specific scheme without storing huge objects in RAM.
    """
    async with httpx.AsyncClient(follow_redirects=True, timeout=20.0) as client:
        response = await client.get(AMFI_URL)
        if response.status_code != 200:
            return None

        # Split line by line using an iterator
        for line in response.text.splitlines():
            line = line.strip()
            # Valid data lines are semicolon-separated with at least 6 tokens
            if not line or ";" not in line:
                continue

            parts = line.split(";")
            # Format: Scheme Code;ISIN Div;ISIN Reinv;Scheme Name;Plan;Option;NAV;Date
            # Example: 135762;...;Axis Children's Fund;Direct Plan;Growth Option;29.9628;11-Sep-2026
            if len(parts) >= 6 and parts[0].strip() == str(scheme_code).strip():
                # Handle varying formats in AMFI (some have 6 columns, newer have 8)
                if len(parts) >= 8:
                    nav_val = parts[6].strip()
                    nav_date = parts[7].strip()
                    scheme_name = f"{parts[3].strip()} - {parts[4].strip()} ({parts[5].strip()})"
                else:
                    nav_val = parts[4].strip()
                    nav_date = parts[5].strip()
                    scheme_name = parts[3].strip()

                try:
                    nav_float = float(nav_val)
                except ValueError:
                    nav_float = 0.0

                return {
                    "scheme_code": parts[0].strip(),
                    "scheme_name": scheme_name,
                    "nav": nav_float,
                    "date": nav_date
                }

    return None