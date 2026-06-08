import json
import random
import shutil
import sys
from pathlib import Path

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, Header, HTTPException, Query, UploadFile
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError

load_dotenv()
BASE_DIR = Path(__file__).resolve().parents[1]

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from ai_engine import opening_question, next_question, roadmap
    from auth import create_token, decode_token, hash_password, verify_password
    from coding import PROBLEMS, evaluate_code
    from database import UPLOAD_DIR, get_db, init_db
    from jobs import fetch_live_jobs, suggested_job_query
    from reports import build_report
    from resume import analyze_resume, extract_text
else:
    from .ai_engine import opening_question, next_question, roadmap
    from .auth import create_token, decode_token, hash_password, verify_password
    from .coding import PROBLEMS, evaluate_code
    from .database import UPLOAD_DIR, get_db, init_db
    from .jobs import fetch_live_jobs, suggested_job_query
    from .reports import build_report
    from .resume import analyze_resume, extract_text


app = FastAPI(title="AI Interview Simulator", version="1.0.0")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


class RegisterRequest(BaseModel):
    name: str
    email: str
    password: str
    role: str = "candidate"


class LoginRequest(BaseModel):
    email: str
    password: str


class InterviewStartRequest(BaseModel):
    role: str
    level: str
    interview_type: str
    company: str = "Generic"


class AnswerRequest(BaseModel):
    answer: str


class CodeRequest(BaseModel):
    language: str
    problem_title: str
    code: str


@app.on_event("startup")
def startup() -> None:
    init_db()


def current_user(authorization: str = Header(default=""), token: str = "") -> dict:
    bearer = authorization.replace("Bearer ", "", 1)
    payload = decode_token(bearer or token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    with get_db() as db:
        user = db.execute("SELECT id, name, email, role FROM users WHERE id = ?", (payload["sub"],)).fetchone()
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        return dict(user)


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return (BASE_DIR / "static" / "index.html").read_text(encoding="utf-8")


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/api/auth/register")
def register(payload: RegisterRequest) -> dict:
    with get_db() as db:
        try:
            cur = db.execute(
                "INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, ?)",
                (payload.name, payload.email.lower(), hash_password(payload.password), payload.role),
            )
        except IntegrityError:
            raise HTTPException(status_code=409, detail="Email already registered")
        token = create_token({"sub": cur.lastrowid, "role": payload.role})
        return {"token": token, "user": {"id": cur.lastrowid, "name": payload.name, "email": payload.email, "role": payload.role}}


@app.post("/api/auth/login")
def login(payload: LoginRequest) -> dict:
    with get_db() as db:
        user = db.execute("SELECT * FROM users WHERE email = ?", (payload.email.lower(),)).fetchone()
        if not user or not verify_password(payload.password, user["password_hash"]):
            raise HTTPException(status_code=401, detail="Invalid email or password")
        token = create_token({"sub": user["id"], "role": user["role"]})
        return {"token": token, "user": {"id": user["id"], "name": user["name"], "email": user["email"], "role": user["role"]}}


@app.get("/api/me")
def me(user: dict = Depends(current_user)) -> dict:
    return user


@app.post("/api/resumes")
def upload_resume(file: UploadFile = File(...), user: dict = Depends(current_user)) -> dict:
    safe_name = f"{user['id']}_{file.filename.replace(' ', '_')}"
    path = UPLOAD_DIR / safe_name
    with path.open("wb") as out:
        shutil.copyfileobj(file.file, out)
    text = extract_text(path)
    analysis = analyze_resume(text)
    with get_db() as db:
        cur = db.execute(
            """
            INSERT INTO resumes (user_id, filename, text, skills, education, experience, projects, certifications)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user["id"],
                file.filename,
                text,
                json.dumps(analysis["skills"]),
                analysis["education"],
                analysis["experience"],
                analysis["projects"],
                analysis["certifications"],
            ),
        )
    return {"id": cur.lastrowid, **analysis}


@app.post("/api/interviews")
def start_interview(payload: InterviewStartRequest, user: dict = Depends(current_user)) -> dict:
    with get_db() as db:
        resume = db.execute("SELECT skills, projects FROM resumes WHERE user_id = ? ORDER BY id DESC LIMIT 1", (user["id"],)).fetchone()
        seeds = []
        if resume:
            skills = json.loads(resume["skills"])
            seeds = [f"Explain your experience with {skill} from your resume." for skill in skills[:3]]
            if resume["projects"] != "Not detected":
                seeds.insert(0, "Explain one resume project end-to-end, including your technical choices.")
        cur = db.execute(
            "INSERT INTO interviews (user_id, role, level, interview_type, company) VALUES (?, ?, ?, ?, ?)",
            (user["id"], payload.role, payload.level, payload.interview_type, payload.company),
        )
        previous_questions = db.execute(
            """
            SELECT interview_messages.content
            FROM interview_messages
            JOIN interviews ON interviews.id = interview_messages.interview_id
            WHERE interviews.user_id = ?
              AND interviews.role = ?
              AND interviews.interview_type = ?
              AND interview_messages.sender = 'AI'
            ORDER BY interview_messages.id DESC
            LIMIT 30
            """,
            (user["id"], payload.role, payload.interview_type),
        ).fetchall()
        asked_questions = [row["content"] for row in previous_questions]
        first = opening_question(payload.role, payload.level, payload.interview_type, payload.company, seeds, asked_questions)
        db.execute(
            "INSERT INTO interview_messages (interview_id, sender, agent, content) VALUES (?, ?, ?, ?)",
            (cur.lastrowid, "AI", first["agent"], first["question"]),
        )
        return {"id": cur.lastrowid, "agent": first["agent"], "question": first["question"]}


@app.post("/api/interviews/{interview_id}/answer")
async def answer_interview(interview_id: int, payload: AnswerRequest, user: dict = Depends(current_user)) -> dict:
    with get_db() as db:
        interview = db.execute("SELECT * FROM interviews WHERE id = ? AND user_id = ?", (interview_id, user["id"])).fetchone()
        if not interview:
            raise HTTPException(status_code=404, detail="Interview not found")
        rows = db.execute("SELECT sender, agent, content FROM interview_messages WHERE interview_id = ? ORDER BY id", (interview_id,)).fetchall()
        history = [dict(row) for row in rows]
        db.execute(
            "INSERT INTO interview_messages (interview_id, sender, agent, content) VALUES (?, ?, ?, ?)",
            (interview_id, "Candidate", "Candidate", payload.answer),
        )
        result = await next_question(
            interview["role"], interview["level"], interview["interview_type"], interview["company"], history, payload.answer
        )
        db.execute(
            "INSERT INTO interview_messages (interview_id, sender, agent, content, score_json) VALUES (?, ?, ?, ?, ?)",
            (interview_id, "AI", result["agent"], result["question"], json.dumps(result["score"])),
        )
        db.execute("UPDATE interviews SET current_agent = ?, overall_score = ? WHERE id = ?", (result["agent"], result["score"]["overall_score"], interview_id))
    return result


@app.post("/api/interviews/{interview_id}/finish")
def finish_interview(interview_id: int, user: dict = Depends(current_user)) -> dict:
    with get_db() as db:
        interview = db.execute("SELECT * FROM interviews WHERE id = ? AND user_id = ?", (interview_id, user["id"])).fetchone()
        if not interview:
            raise HTTPException(status_code=404, detail="Interview not found")
        messages = db.execute("SELECT * FROM interview_messages WHERE interview_id = ? ORDER BY id", (interview_id,)).fetchall()
        report = build_report(dict(interview), [dict(m) for m in messages])
        db.execute("UPDATE interviews SET status = 'completed', completed_at = CURRENT_TIMESTAMP WHERE id = ?", (interview_id,))
        cur = db.execute("INSERT INTO reports (interview_id, report_html) VALUES (?, ?)", (interview_id, report))
        return {"report_id": cur.lastrowid, "download_url": f"/api/reports/{cur.lastrowid}"}


@app.get("/api/reports/{report_id}")
def get_report(report_id: int, download: bool = False, user: dict = Depends(current_user)) -> Response:
    with get_db() as db:
        row = db.execute(
            """
            SELECT reports.report_html FROM reports
            JOIN interviews ON interviews.id = reports.interview_id
            WHERE reports.id = ? AND interviews.user_id = ?
            """,
            (report_id, user["id"]),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Report not found")
        if download:
            return Response(
                row["report_html"],
                media_type="text/html",
                headers={"Content-Disposition": f'attachment; filename="interview_report_{report_id}.html"'},
            )
        return HTMLResponse(row["report_html"])


@app.get("/api/interviews")
def list_interviews(user: dict = Depends(current_user)) -> dict:
    with get_db() as db:
        rows = db.execute("SELECT * FROM interviews WHERE user_id = ? ORDER BY id DESC", (user["id"],)).fetchall()
        return {"interviews": [dict(row) for row in rows]}


@app.get("/api/analytics")
def analytics(user: dict = Depends(current_user)) -> dict:
    with get_db() as db:
        rows = db.execute("SELECT * FROM interviews WHERE user_id = ? ORDER BY id", (user["id"],)).fetchall()
        interviews = [dict(row) for row in rows]
        scores = [row["overall_score"] for row in interviews if row["overall_score"]]
        message_rows = db.execute(
            """
            SELECT interview_messages.score_json
            FROM interview_messages
            JOIN interviews ON interviews.id = interview_messages.interview_id
            WHERE interviews.user_id = ? AND interview_messages.score_json IS NOT NULL
            """,
            (user["id"],),
        ).fetchall()
        score_cards = []
        for row in message_rows:
            try:
                score_cards.append(json.loads(row["score_json"]))
            except (TypeError, json.JSONDecodeError):
                continue
        weak_topics, strong_topics = _topic_insights(score_cards)
        return {
            "total_interviews": len(interviews),
            "average_score": round(sum(scores) / len(scores), 1) if scores else 0,
            "trend": scores[-8:],
            "strong_topics": strong_topics,
            "weak_topics": weak_topics,
            "roadmap": roadmap(scores, weak_topics),
        }


def _topic_insights(score_cards: list[dict]) -> tuple[list[str], list[str]]:
    categories = {
        "technical_score": "Technical knowledge",
        "communication_score": "Communication",
        "confidence_score": "Confidence",
        "clarity_score": "Clarity",
        "answer_completeness_score": "Answer completeness",
    }
    averages = {}
    for key, label in categories.items():
        values = [float(card[key]) for card in score_cards if isinstance(card.get(key), (int, float))]
        if values:
            averages[label] = sum(values) / len(values)

    weak_topics = [
        label for label, average in sorted(averages.items(), key=lambda item: item[1])
        if average < 7
    ]
    strong_topics = [
        label for label, average in sorted(averages.items(), key=lambda item: item[1], reverse=True)
        if average >= 8
    ]
    return weak_topics[:3], strong_topics[:3]


@app.get("/api/coding/problems")
def coding_problems(user: dict = Depends(current_user)) -> dict:
    with get_db() as db:
        rows = db.execute(
            "SELECT problem_title FROM coding_results WHERE user_id = ? ORDER BY id DESC",
            (user["id"],),
        ).fetchall()
    attempted = {row["problem_title"] for row in rows}
    problems = list(PROBLEMS)
    random.shuffle(problems)
    problems.sort(key=lambda problem: problem["title"] in attempted)
    return {"problems": problems}


@app.get("/api/jobs")
def jobs(search: str = Query(default="", max_length=120), user: dict = Depends(current_user)) -> dict:
    query = search.strip()
    skills = []
    latest_role = ""
    if not query:
        with get_db() as db:
            resume = db.execute("SELECT skills FROM resumes WHERE user_id = ? ORDER BY id DESC LIMIT 1", (user["id"],)).fetchone()
            interview = db.execute("SELECT role FROM interviews WHERE user_id = ? ORDER BY id DESC LIMIT 1", (user["id"],)).fetchone()
        if resume:
            try:
                skills = json.loads(resume["skills"])
            except (TypeError, json.JSONDecodeError):
                skills = []
        latest_role = interview["role"] if interview else ""
        query = suggested_job_query(latest_role, skills)
    result = fetch_live_jobs(query)
    result["suggested_from"] = latest_role or (", ".join(skills[:3]) if skills else "default software role")
    return result


@app.post("/api/coding/run")
def run_code(payload: CodeRequest, user: dict = Depends(current_user)) -> dict:
    result = evaluate_code(payload.language, payload.code, payload.problem_title)
    with get_db() as db:
        db.execute(
            "INSERT INTO coding_results (user_id, language, problem_title, code, result_json) VALUES (?, ?, ?, ?, ?)",
            (user["id"], payload.language, payload.problem_title, payload.code, json.dumps(result)),
        )
    return result


@app.get("/api/admin/overview")
def admin_overview(user: dict = Depends(current_user)) -> dict:
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    with get_db() as db:
        return {
            "users": db.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"],
            "interviews": db.execute("SELECT COUNT(*) AS c FROM interviews").fetchone()["c"],
            "completed": db.execute("SELECT COUNT(*) AS c FROM interviews WHERE status = 'completed'").fetchone()["c"],
        }


if __name__ == "__main__":
    import os

    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=int(os.getenv("PORT", "8000")))
