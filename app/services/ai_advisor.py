import html
import os
import re
import httpx
from groq import AsyncGroq
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

groq_client = AsyncGroq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

async def generate_portfolio_briefing(analytics_data: dict) -> str:
    if not groq_client:
        return "AI analysis unavailable: Missing GROQ_API_KEY."

    summary = (
        f"As-of Date: {analytics_data.get('as_of_date')}\n"
        f"Total Invested: Rs {analytics_data.get('total_invested')}\n"
        f"Current Market Value: Rs {analytics_data.get('current_value')}\n"
        f"Overall P&L: Rs {analytics_data.get('total_pnl')} ({analytics_data.get('percentage_return')}%)\n"
        f"Today's 1-Day P&L: Rs {analytics_data.get('daily_pnl')} ({analytics_data.get('daily_percentage')}%)\n"
        f"Fund Performance:\n"
    )
    for fund in analytics_data.get("funds", []):
        summary += (
            f"- {fund['scheme_name']}: Value Rs {fund['current_value']}, "
            f"Total P&L Rs {fund['total_pnl']}, Daily P&L Rs {fund['daily_pnl']}\n"
        )

    system_prompt = (
        "You are an expert, objective financial portfolio analyst. "
        "Review the mutual fund portfolio telemetry and output exactly 3 concise bullet points:\n"
        "1. Overall portfolio health and 1-day momentum.\n"
        "2. Top positive contributor vs. biggest drag today.\n"
        "3. A disciplined takeaway for long-term compounding.\n"
        "Do not output chain-of-thought, reasoning steps, or markdown tags."
    )

    try:
        # Use qwen/qwen3.8-27b for direct conversational responses
        response = await groq_client.chat.completions.create(
            model="qwen/qwen3.8-27b",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": summary}
            ],
            temperature=0.3,
            max_tokens=250
        )
        raw_text = response.choices[0].message.content or ""
        
        # Remove any stray <think> or <thought> reasoning blocks if present
        cleaned_text = re.sub(r"<think>.*?</think>", "", raw_text, flags=re.DOTALL).strip()
        cleaned_text = re.sub(r"<thought>.*?</thought>", "", cleaned_text, flags=re.DOTALL).strip()

        print("\n--- [DEBUG: GROQ AI INSIGHTS OUTPUT] ---")
        print(cleaned_text)
        print("----------------------------------------\n")

        return html.escape(cleaned_text)
    except Exception as e:
        print(f"[Groq Error]: {e}")
        return f"Could not generate insights: {str(e)}"

async def send_telegram_alert(message: str) -> bool:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        return False

    telegram_url = f"https://api.telegram.org/bot{token}/sendMessage"

    async with httpx.AsyncClient(timeout=12.0) as client:
        res = await client.post(
            telegram_url,
            json={"chat_id": chat_id, "text": message, "parse_mode": "HTML"}
        )
        if res.status_code == 200:
            return True

        # Fallback to plain text if HTML entity parsing encounters an issue
        print(f"[Telegram HTML Error] ({res.text}), falling back to plain text...")
        fallback = await client.post(
            telegram_url,
            json={"chat_id": chat_id, "text": message}
        )
        return fallback.status_code == 200