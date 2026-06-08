# AI Interview Simulator using LLMs

An AI-powered mock interview platform built with FastAPI, Streamlit, PostgreSQL (Supabase), and LLM-based adaptive interview logic.

The platform supports:
- Candidate authentication
- Resume upload and parsing
- AI-driven interview sessions
- Adaptive follow-up questions
- Coding assessments
- Analytics dashboards
- Interview reports
- Admin APIs

---

# Tech Stack

- FastAPI
- Streamlit
- SQLAlchemy
- PostgreSQL (Supabase)
- OpenAI API (optional)
- Gunicorn
- Render (backend deployment)

---

# Local Development Setup

## 1. Install dependencies

```powershell
python -m pip install -r requirements.txt
```

---

## 2. Configure environment variables

Create a `.env` file from `.env.example`.

Example:

```env
OPENAI_API_KEY=your_openai_key
FASTAPI_BASE_URL=http://127.0.0.1:8000

DATABASE_URL=postgresql+psycopg2://postgres:YOUR_PASSWORD@db.xxxxx.supabase.co:5432/postgres?sslmode=require

TOKEN_SECRET=replace-with-a-long-random-secret

PORT=8000
```

---

## 3. Run FastAPI backend

```powershell
python -m uvicorn app.main:app --reload
```

Backend runs at:

```txt
http://127.0.0.1:8000
```

---

## 4. Run Streamlit frontend

Open a second terminal:

```powershell
python -m streamlit run streamlit_app.py
```

---

# Production Deployment

## Backend Deployment (Render)

### Build Command

```bash
pip install -r requirements.txt
```

### Start Command

```bash
gunicorn -w 1 -k uvicorn.workers.UvicornWorker app.main:app
```

---

## Render Environment Variables

Add these in Render Dashboard:

```env
OPENAI_API_KEY=your_openai_key

FASTAPI_BASE_URL=https://your-backend-url.onrender.com

DATABASE_URL=postgresql+psycopg2://postgres:YOUR_PASSWORD@db.xxxxx.supabase.co:5432/postgres?sslmode=require

TOKEN_SECRET=replace-with-a-long-random-secret

PORT=8000
```

---

# Frontend Deployment (Streamlit Cloud)

Deploy `streamlit_app.py` on Streamlit Cloud.

Set the Streamlit Cloud main file path to:

```txt
streamlit_app.py
```

In Streamlit secrets/config:

```env
FASTAPI_BASE_URL=https://your-backend-url.onrender.com
```

---

# Features

## Authentication
- User registration
- Secure login
- Bearer token authentication

---

## Resume Analyzer
- Upload PDF, DOCX, TXT resumes
- Skill extraction
- Education extraction
- Experience analysis
- Project analysis

---

## AI Interview Engine
- Technical interviews
- HR interviews
- Behavioral interviews
- Managerial interviews
- Adaptive follow-up questions
- Multi-agent interviewer simulation

---

## Scoring System

Tracks:
- Technical knowledge
- Communication
- Confidence
- Clarity
- Answer completeness

---

## Coding Module

Supports:
- Python execution
- Java review
- JavaScript review
- SQL review

---

## Analytics Dashboard

Includes:
- Score trends
- Strong topics
- Weak topics
- Interview history
- AI-generated improvement roadmap

---

## Report Generation

- Downloadable HTML reports
- Interview summaries
- Performance insights

---

# Database

The project uses PostgreSQL via Supabase only.

Set `DATABASE_URL` to your Supabase PostgreSQL connection string:

```env
DATABASE_URL=postgresql+psycopg2://postgres:YOUR_PASSWORD@db.YOUR_PROJECT_REF.supabase.co:5432/postgres?sslmode=require
```

SQLAlchemy automatically creates the required tables during startup.

No manual database creation is required.

---

# OpenAI Integration

If `OPENAI_API_KEY` is not provided:
- The application automatically switches to deterministic fallback mode.
- Interviews still work using rule-based logic.

---

# API Health Check

```txt
GET /api/health
```

Expected response:

```json
{
  "status": "ok"
}
```

---

# Useful Commands

## Git Push

```bash
git add .
git commit -m "update project"
git push origin main
```

---

## Render Logs

```txt
Render Dashboard → Service → Logs
```

---

# Folder Structure

```txt
app/
 ├── main.py
 ├── database.py
 ├── ai_engine.py
 ├── auth.py
 ├── coding.py
 ├── jobs.py
 ├── reports.py
 ├── resume.py

static/
uploads/

streamlit_app.py
requirements.txt
README.md
```

---

# Important Notes

- Use `DATABASE_URL` for local development and production deployment.
- The database connection must be PostgreSQL/Supabase.
- Supabase requires:

```txt
?sslmode=require
```

in the PostgreSQL connection string.

- Render free tier may sleep after inactivity and take 30–60 seconds to wake up.
