import os
import sys
import httpx
from sqlalchemy import create_engine, text

# Get environment variables
db_url = os.getenv("DATABASE_URL")
telegram_token = os.getenv("TELEGRAM_TOKEN")
chat_id = os.getenv("MY_CHAT_ID")
command_text = os.getenv("COMMAND_TEXT", "")

def send_telegram(message: str):
    url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
    httpx.post(url, json={"chat_id": chat_id, "text": message, "parse_mode": "HTML"})

def process_update():
    try:
        # Example command: /update 120716 25000 150.5
        parts = command_text.split()
        if len(parts) != 4:
            send_telegram("❌ <b>Format Error</b>\nUse: <code>/update scheme_code amount units</code>\nExample: <code>/update 120716 25000 150.5</code>")
            return

        scheme_code = parts[1]
        amount_added = float(parts[2])
        units_added = float(parts[3])

        engine = create_engine(db_url)
        with engine.begin() as conn:
            # Check if fund exists in holdings
            result = conn.execute(text("SELECT total_units, invested_amount FROM holdings WHERE scheme_code = :code"), {"code": scheme_code}).fetchone()
            
            if not result:
                send_telegram(f"❌ Fund <b>{scheme_code}</b> not found in your portfolio.")
                return

            # Update the database
            new_units = result.total_units + units_added
            new_invested = result.invested_amount + amount_added
            
            conn.execute(
                text("UPDATE holdings SET total_units = :units, invested_amount = :invested WHERE scheme_code = :code"),
                {"units": new_units, "invested": new_invested, "code": scheme_code}
            )

        send_telegram(
            f"✅ <b>SIP Logged Successfully!</b>\n\n"
            f"<b>Scheme:</b> {scheme_code}\n"
            f"<b>Amount Added:</b> ₹{amount_added:,.2f}\n"
            f"<b>Units Added:</b> {units_added}\n"
            f"<b>New Total Invested:</b> ₹{new_invested:,.2f}"
        )

    except Exception as e:
        send_telegram(f"❌ <b>Database Error:</b>\n{str(e)}")

if __name__ == "__main__":
    process_update()