# AI Interview Simulator using LLMs

A full-stack FastAPI application for AI-powered mock interviews. It includes candidate authentication, resume upload and parsing, role-based interview sessions, adaptive follow-up questions, scoring, coding practice, analytics, and report generation.

## Run locally

```powershell
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000`.

## Streamlit frontend

Run the FastAPI backend first, then start Streamlit:

```powershell
python -m uvicorn app.main:app --reload
python -m streamlit run streamlit_app.py
```

For Streamlit deployment, set `FASTAPI_BASE_URL` to your deployed backend URL,
for example your Railway web service URL.

## What is included

- Candidate registration and login with signed bearer tokens.
- Resume upload for PDF, DOCX, and TXT files.
- Role, level, company, and interview-type based sessions.
- Multi-agent panel styles: HR, technical, manager, behavioral.
- LLM-ready interview engine with deterministic fallback mode.
- Structured scoring for technical quality, communication, confidence, clarity, and completeness.
- Coding challenge module with Python execution and SQL/Java/JavaScript review scaffolding.
- Analytics dashboard with score trends, weak topics, strengths, and history.
- Downloadable HTML interview reports.
- Admin-friendly API surfaces for templates and interview history.

## Environment

Copy `.env.example` to `.env` and fill in your local values:

```env
OPENAI_API_KEY=your_key_here
FASTAPI_BASE_URL=http://127.0.0.1:8000
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=root
DB_PASSWORD=change-me
DB_NAME=AI_interview_simulator
TOKEN_SECRET=replace-with-a-long-random-secret
PORT=8000
```

The app works without `OPENAI_API_KEY`; it will use a local rules-based simulator.

The app creates the MySQL database `AI_interview_simulator` automatically if the configured user has permission.
On Railway, attach a MySQL service and the app will read Railway's `MYSQLHOST`,
`MYSQLPORT`, `MYSQLUSER`, `MYSQLPASSWORD`, `MYSQLDATABASE`, or `MYSQL_URL`
variables automatically.
