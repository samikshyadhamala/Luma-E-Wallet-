# Luma Wallet

Luma Wallet is a Django e-wallet project set up for Nepalese Rupees (NPR). It includes customer wallet pages and a staff operations area for reviewing KYC submissions, flagged transactions, refunds, wallets, and users.

## Features

- Account registration and email OTP login
- KYC submission and staff review
- Wallet top-ups, withdrawals, and transfers
- Transaction PIN checks, transaction history, and ledger records
- Behavioral transaction risk scoring with CatBoost
- Budgets, savings goals, and downloadable Excel statements
- Staff review tools for risk flags, refunds, and account status

## Requirements

- Python 3.12 or a compatible Python version
- pip

The project dependencies are listed in `requirements.txt`.

## Run locally

From the project root, create and activate a virtual environment, install dependencies, apply database migrations, and start Django:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

On Windows PowerShell, activate the environment with:

```powershell
.venv\Scripts\Activate.ps1
```

Open <http://127.0.0.1:8000/> in your browser. Create an account through the registration page. Email OTP delivery needs working SMTP settings; for local development, Django's console email backend can display OTP messages in the terminal.

## Environment configuration

Email settings can be supplied through a `.env` file in the project root (it is ignored by Git):

```dotenv
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-address@example.com
EMAIL_HOST_PASSWORD=your-email-app-password
DEFAULT_FROM_EMAIL=your-address@example.com
```

For local development without SMTP, set `EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend` to print email contents in the runserver terminal.

## Fraud model

The transaction risk scorer looks for `behavioral_model_v2.pkl` in the project root. Keep this file in the repository if you want the model available in a deployment. If the file is missing or the model cannot be loaded, transactions continue with risk status `NOT_REVIEWED` and automatic scoring is unavailable.

Only load pickle files from trusted sources: loading a pickle can execute code. The model was serialized with CatBoost, so the deployed CatBoost version should be compatible with the version used to create it.

## Main routes

- `/` — wallet dashboard
- `/account/register/` — create an account
- `/account/login/` — sign in
- `/transactions/` — transaction history
- `/admin/` — staff operations pages
- `/admin/manage/` — Django admin

## Deployment notes

The project currently uses SQLite for local development. Use a managed database for a hosted deployment where data must persist; a serverless deployment's local filesystem should not be treated as durable database storage. Configure a production secret key, turn off Django debug mode, and set allowed hosts and HTTPS security settings before exposing the app publicly. Vercel supports Django and Python functions, but the deployment also needs an appropriate persistent database and correctly configured environment variables.

## Project structure

```text
apps/
  core/
  staff_operations/
  transactions/
  users/
  wallets/
config/       Django project settings and URL configuration
docs/         Project documentation
static/       CSS and other static assets
templates/    Django HTML templates
manage.py     Django management entry point
```
