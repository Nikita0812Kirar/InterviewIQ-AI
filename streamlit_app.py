import os
from typing import Any

import requests
import streamlit as st
from dotenv import load_dotenv


load_dotenv()

st.set_page_config(page_title="InterviewIQ AI", page_icon="IQ", layout="wide")

CONNECT_TIMEOUT = 10
READ_TIMEOUT = 180


def api_base_url() -> str:
    try:
        secret_url = st.secrets.get("FASTAPI_BASE_URL", "") or st.secrets.get("API_BASE_URL", "")
    except Exception:
        secret_url = ""
    return (secret_url or os.getenv("FASTAPI_BASE_URL") or os.getenv("API_BASE_URL") or "").rstrip("/")


API_URL = api_base_url()


def init_state() -> None:
    st.session_state.setdefault("api_url", API_URL)
    st.session_state.setdefault("token", "")
    st.session_state.setdefault("user", None)
    st.session_state.setdefault("interview_id", None)
    st.session_state.setdefault("messages", [])


def backend_url() -> str:
    return st.session_state.get("api_url", "").rstrip("/")


def backend_setup_view() -> None:
    st.title("InterviewIQ AI")
    st.warning("FastAPI backend URL is not configured.")
    url = st.text_input(
        "FastAPI backend URL",
        placeholder="https://your-fastapi-backend.example.com",
    ).strip()
    if st.button("Save Backend URL", use_container_width=True):
        if not url:
            st.error("Enter your deployed FastAPI backend URL.")
            return
        if url.startswith("http://127.0.0.1") or url.startswith("http://localhost"):
            st.error("Use a public backend URL for deployed Streamlit apps.")
            return
        st.session_state.api_url = url.rstrip("/")
        st.rerun()


def api_request(method: str, path: str, **kwargs: Any) -> Any:
    api_url = backend_url()
    if not api_url:
        raise RuntimeError(
            "FastAPI backend URL is not configured. Add FASTAPI_BASE_URL in Streamlit secrets or enter it in the app."
        )
    headers = kwargs.pop("headers", {})
    if st.session_state.token:
        headers["Authorization"] = f"Bearer {st.session_state.token}"
    try:
        response = requests.request(
            method,
            f"{api_url}{path}",
            headers=headers,
            timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
            **kwargs,
        )
    except requests.Timeout as exc:
        raise RuntimeError(
            "The backend is taking too long to respond. Check that the FastAPI server is running and try again."
        ) from exc
    except requests.RequestException as exc:
        raise RuntimeError(f"Could not connect to the backend at {api_url}.") from exc
    if response.status_code >= 400:
        try:
            detail = response.json().get("detail", response.text)
        except ValueError:
            detail = response.text
        raise RuntimeError(detail or "Request failed")
    content_type = response.headers.get("content-type", "")
    return response.json() if "application/json" in content_type else response.text


def login_view() -> None:
    st.title("InterviewIQ AI")
    mode = st.radio("Account", ["Login", "Register"], horizontal=True, label_visibility="collapsed")
    with st.form("auth_form"):
        name = ""
        if mode == "Register":
            name = st.text_input("Name")
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Continue", use_container_width=True)

    if submitted:
        try:
            if mode == "Register":
                payload = {"name": name, "email": email, "password": password, "role": "candidate"}
                data = api_request("POST", "/api/auth/register", json=payload)
            else:
                data = api_request("POST", "/api/auth/login", json={"email": email, "password": password})
            st.session_state.token = data["token"]
            st.session_state.user = data["user"]
            st.rerun()
        except RuntimeError as exc:
            st.error(str(exc))


def dashboard_view() -> None:
    st.subheader("Dashboard")
    try:
        with st.spinner("Loading dashboard..."):
            data = api_request("GET", "/api/analytics")
    except RuntimeError as exc:
        st.error(str(exc))
        if st.button("Retry Dashboard"):
            st.rerun()
        return

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Interviews", data["total_interviews"])
    col2.metric("Average Score", data["average_score"])
    col3.metric("Weak Topic", data["weak_topics"][0] if data["weak_topics"] else "None")

    if data["trend"]:
        st.line_chart(data["trend"], height=220)
    st.markdown("#### Career Coach Roadmap")
    for item in data["roadmap"] or ["Complete an interview to generate a personalized roadmap."]:
        st.write(f"- {item}")


def resume_view() -> None:
    st.subheader("Resume")
    uploaded = st.file_uploader("Upload resume", type=["pdf", "docx", "txt"])
    if st.button("Analyze Resume", disabled=uploaded is None):
        try:
            files = {"file": (uploaded.name, uploaded.getvalue(), uploaded.type)}
            data = api_request("POST", "/api/resumes", files=files)
            st.json(data)
        except RuntimeError as exc:
            st.error(str(exc))


def interview_view() -> None:
    st.subheader("Interview Room")
    roles = [
        "Data Analyst",
        "Data Scientist",
        "Python Developer",
        "Frontend Developer",
        "Backend Developer",
        "Full Stack Developer",
        "SQL Developer",
        "HR Interview",
        "Behavioral Interview",
    ]
    col1, col2, col3, col4 = st.columns(4)
    role = col1.selectbox("Role", roles)
    level = col2.selectbox("Level", ["Beginner", "Intermediate", "Advanced"])
    interview_type = col3.selectbox("Type", ["Technical", "HR", "Behavioral", "Case Study", "Panel"])
    company = col4.selectbox("Company", ["Generic", "Google", "Amazon", "Microsoft", "TCS", "Infosys", "Accenture"])

    if st.button("Start Interview", use_container_width=True):
        try:
            data = api_request(
                "POST",
                "/api/interviews",
                json={"role": role, "level": level, "interview_type": interview_type, "company": company},
            )
            st.session_state.interview_id = data["id"]
            st.session_state.messages = [{"sender": "AI", "agent": data["agent"], "content": data["question"]}]
        except RuntimeError as exc:
            st.error(str(exc))

    for message in st.session_state.messages:
        with st.chat_message("user" if message["sender"] == "Candidate" else "assistant"):
            st.caption(message.get("agent", message["sender"]))
            st.write(message["content"])
            if message.get("score"):
                st.info(f"Score: {message['score']['overall_score']}/10 - {message['score']['feedback']}")

    answer = st.chat_input("Type your answer")
    if answer and st.session_state.interview_id:
        st.session_state.messages.append({"sender": "Candidate", "agent": "Candidate", "content": answer})
        try:
            data = api_request("POST", f"/api/interviews/{st.session_state.interview_id}/answer", json={"answer": answer})
            st.session_state.messages.append(
                {"sender": "AI", "agent": data["agent"], "content": data["question"], "score": data["score"]}
            )
            st.rerun()
        except RuntimeError as exc:
            st.error(str(exc))

    if st.session_state.interview_id and st.button("Finish and Generate Report"):
        try:
            data = api_request("POST", f"/api/interviews/{st.session_state.interview_id}/finish")
            st.success("Report generated.")
            st.link_button("Open Report", f"{backend_url()}{data['download_url']}?token={st.session_state.token}")
        except RuntimeError as exc:
            st.error(str(exc))


def coding_view() -> None:
    st.subheader("Coding Room")
    try:
        data = api_request("GET", "/api/coding/problems")
    except RuntimeError as exc:
        st.error(str(exc))
        return

    problems = data["problems"]
    titles = [f"{problem['title']} - {problem['difficulty']}" for problem in problems]
    selected = st.selectbox("Problem", range(len(problems)), format_func=lambda index: titles[index])
    problem = problems[selected]
    st.write(problem["prompt"])
    language = st.selectbox("Language", ["Python", "Java", "JavaScript", "SQL"])
    code = st.text_area("Code", value=problem["starter"], height=280)
    if st.button("Run Tests"):
        try:
            result = api_request(
                "POST",
                "/api/coding/run",
                json={"language": language, "problem_title": problem["title"], "code": code},
            )
            st.json(result)
        except RuntimeError as exc:
            st.error(str(exc))


def jobs_view() -> None:
    st.subheader("Jobs")
    query = st.text_input("Search", placeholder="Python, data analyst, React, SQL")
    if st.button("Search Jobs") or not query:
        try:
            path = f"/api/jobs?search={query}" if query else "/api/jobs"
            data = api_request("GET", path)
            st.caption(data.get("error") or f"{len(data['jobs'])} jobs from {data['source']} for {data['query']}")
            for job in data["jobs"]:
                with st.container(border=True):
                    st.markdown(f"#### {job['title']}")
                    st.write(f"{job['company']} | {job['location']} | {job['salary']}")
                    st.write(job["summary"])
                    st.link_button("Apply", job["url"])
        except RuntimeError as exc:
            st.error(str(exc))


def reports_view() -> None:
    st.subheader("Reports")
    try:
        data = api_request("GET", "/api/interviews")
    except RuntimeError as exc:
        st.error(str(exc))
        return

    for interview in data["interviews"]:
        with st.container(border=True):
            st.write(f"{interview['role']} | {interview['level']} | {interview['company']}")
            st.caption(f"{interview['status']} | Score: {interview['overall_score']}/10 | {interview['created_at']}")


def main() -> None:
    init_state()
    if not backend_url():
        backend_setup_view()
        return

    if not st.session_state.token:
        login_view()
        return

    user = st.session_state.user or {}
    with st.sidebar:
        st.markdown("### InterviewIQ AI")
        st.caption(f"{user.get('name', '')} - {user.get('role', '')}")
        page = st.radio("Navigate", ["Dashboard", "Resume", "Interview", "Coding", "Jobs", "Reports"])
        if st.button("Logout", use_container_width=True):
            st.session_state.token = ""
            st.session_state.user = None
            st.session_state.interview_id = None
            st.session_state.messages = []
            st.rerun()

    {
        "Dashboard": dashboard_view,
        "Resume": resume_view,
        "Interview": interview_view,
        "Coding": coding_view,
        "Jobs": jobs_view,
        "Reports": reports_view,
    }[page]()


if __name__ == "__main__":
    main()
