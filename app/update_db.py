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
        engine = create_engine(db_url)
        
        # --- NEW SPEND LOGIC ---
        if command_text.startswith("/spend"):
            CATEGORY_MAP = {
                "f": "Food & Dining",
                "t": "Travel & Fuel",
                "g": "Groceries",
                "b": "Bills & Utilities",
                "m": "Miscellaneous"
            }
            
            # Example format: /spend 450 f Lunch at canteen
            parts = command_text.strip().split(maxsplit=3)
            if len(parts) < 3:
                send_telegram("❌ <b>Format Error</b>\nUse: <code>/spend amount category_code note</code>\nExample: <code>/spend 450 f Lunch</code>")
                return
                
            try:
                amount = float(parts[1])
            except ValueError:
                send_telegram("❌ Invalid amount provided.")
                return
                
            cat_code = parts[2].lower()
            category = CATEGORY_MAP.get(cat_code, "Uncategorized")
            note = parts[3] if len(parts) > 3 else ""
            
            with engine.begin() as conn:
                conn.execute(
                    text("INSERT INTO expenses (amount, category, note) VALUES (:amt, :cat, :note)"),
                    {"amt": amount, "cat": category, "note": note}
                )
                
            send_telegram(
                f"✅ <b>Expense Logged!</b>\n"
                f"<b>Amount:</b> ₹{amount:,.2f}\n"
                f"<b>Category:</b> {category}\n"
                f"<b>Note:</b> {note}"
            )
            return

        # --- EXISTING UPDATE LOGIC ---
        parts = command_text.split()
        if len(parts) != 4:
            send_telegram("❌ <b>Format Error</b>\nUse: <code>/update scheme_code amount units</code>\nExample: <code>/update 120716 25000 150.5</code>")
            return

        scheme_code = parts[1]
        amount_added = float(parts[2])
        units_added = float(parts[3])

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