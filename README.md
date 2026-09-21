# PortfolioPulse 📈

A serverless, automated personal finance and mutual fund portfolio tracker. This project uses a Telegram Bot interface to log daily expenses and track Systematic Investment Plans (SIPs), routing data through GitHub Actions into a serverless Neon PostgreSQL database.

## 🚀 Features

*   **Automated Mutual Fund Tracking:** Log monthly SIPs, update total units, and track invested amounts via simple Telegram commands.
*   **Frictionless Expense Logging:** Categorize and record daily spending directly from Telegram.
*   **100% Serverless Architecture:** Runs entirely on GitHub Actions (triggered via webhooks and cron schedules), resulting in zero 24/7 server hosting costs.
*   **Secure Data Storage:** Financial data is safely stored in a remote Neon PostgreSQL database, keeping sensitive numbers out of the codebase.

## 🏗️ Architecture

*   **Frontend:** Telegram Bot API
*   **Backend Task Runner:** GitHub Actions (`update_db.yml`, `portfolio_schedule.yml`)
*   **Database:** Neon (Serverless PostgreSQL)
*   **Language:** Python 3 (SQLAlchemy, httpx)

## 📂 Repository Structure

```text
PORTFOLIO_PULSE/
├── .github/
│   └── workflows/
│       ├── portfolio_schedule.yml   # Cron jobs for automated briefings
│       └── update_db.yml            # Webhook listener for Telegram commands
├── app/
│   ├── services/                    # Core business logic and analytics
│   ├── __init__.py                  # Package initialization
│   ├── database.py                  # Database connection handling
│   ├── main.py                      # Future FastAPI dashboard entry point
│   └── models.py                    # SQLAlchemy schema models
├── .env                             # Local secrets (Ignored in Git)
├── .gitignore                       # Git ignore rules
├── requirements.txt                 # Python dependencies
├── run_briefing.py                  # Scheduled portfolio summary generator
└── update_db.py                     # Core command processing script
```
### GitHub Secrets Configuration

To keep your data secure, the following environment variables must be added to your repository under Settings > Secrets and variables > Actions:

**DATABASE_URL:** Your Neon PostgreSQL connection string.

**TELEGRAM_BOT_TOKEN:** Your Telegram Bot API token (from @BotFather).

**TELEGRAM_CHAT_ID:** Your personal Telegram Chat ID (to restrict access).

### Telegram Webhook Setup

Link your Telegram Bot to trigger the .github/workflows/update_db.yml file using a Cloudflare Worker or a direct GitHub repository dispatch webhook.

## 🔒 Security Note
This repository contains structural code only. All sensitive financial records are stored in the Neon database, and all authentication tokens are managed via GitHub Secrets. Never commit .env files to this repository.
