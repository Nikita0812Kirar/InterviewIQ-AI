import json
import os
import random
import re


ROLE_TOPICS = {
    "Data Analyst": ["SQL joins", "dashboard KPIs", "Excel modeling", "Power BI storytelling"],
    "Data Scientist": ["feature engineering", "model evaluation", "bias variance", "deployment"],
    "Python Developer": ["data structures", "OOP", "APIs", "testing"],
    "Frontend Developer": ["React state", "accessibility", "performance", "responsive UI"],
    "Backend Developer": ["REST APIs", "databases", "auth", "scalability"],
    "Full Stack Developer": ["system design", "frontend-backend contracts", "auth", "deployment"],
    "SQL Developer": ["CTEs", "window functions", "indexing", "query optimization"],
    "HR Interview": ["motivation", "team fit", "strengths", "career goals"],
    "Behavioral Interview": ["STAR stories", "conflict", "leadership", "ownership"],
}

AGENTS = ["HR Interviewer", "Technical Interviewer", "Manager Interviewer", "Behavioral Interviewer"]


def opening_question(
    role: str,
    level: str,
    interview_type: str,
    company: str,
    resume_seeds: list[str],
    asked_questions: list[str] | None = None,
) -> dict[str, str]:
    asked = _normalize_questions(asked_questions or [])
    candidates = []
    if resume_seeds:
        candidates.extend(resume_seeds)
    if interview_type == "Case Study":
        candidates.extend(
            [
                "Sales dropped 20% in the North region. How would you investigate the problem?",
                "A product has high signups but low paid conversions. How would you diagnose it?",
                "Customer support tickets doubled this month. What data would you inspect first?",
            ]
        )
    elif interview_type == "HR":
        candidates.extend(
            [
                "Tell me about yourself and the role you are targeting.",
                f"Why are you interested in this {role} opportunity at {company}?",
                "What strengths would your last teammate say you bring to a team?",
            ]
        )
    else:
        topics = ROLE_TOPICS.get(role, ["problem solving"])
        candidates.extend(
            [
                f"Let's start with {topic}. Explain it as you would in a {level.lower()} {role} interview."
                for topic in topics
            ]
        )
        candidates.extend(
            [
                f"Describe a recent {role} problem you solved and the trade-offs behind your approach.",
                f"Which {role} skill do you rely on most in real projects, and how do you prove it works?",
            ]
        )
    question = _pick_unasked(candidates, asked)
    return {"agent": _agent_for_type(interview_type), "question": f"{company} style: {question}"}


def score_answer(answer: str, role: str) -> dict[str, object]:
    words = re.findall(r"[A-Za-z0-9+#.]+", answer)
    technical_terms = sum(1 for word in words if word.lower() in _technical_vocab(role))
    length_score = min(10, max(3, len(words) // 12))
    structure_bonus = 1 if any(term in answer.lower() for term in ["first", "then", "because", "impact", "result"]) else 0
    technical_score = min(10, 4 + technical_terms + structure_bonus)
    communication_score = min(10, length_score + structure_bonus)
    confidence_score = 7 if len(words) > 35 else 5
    clarity_score = min(10, 5 + structure_bonus + (1 if "." in answer else 0) + (1 if len(words) > 25 else 0))
    completeness_score = round((technical_score + communication_score + clarity_score) / 3, 1)
    overall = round((technical_score * 0.35 + communication_score * 0.2 + confidence_score * 0.15 + clarity_score * 0.15 + completeness_score * 0.15), 1)
    improvements = []
    if technical_score < 7:
        improvements.append("Add concrete technical details, trade-offs, and implementation choices.")
    if communication_score < 7:
        improvements.append("Structure the answer with situation, action, result, and measurable impact.")
    if clarity_score < 7:
        improvements.append("Use shorter sentences and state the final takeaway clearly.")
    return {
        "technical_score": technical_score,
        "communication_score": communication_score,
        "confidence_score": confidence_score,
        "clarity_score": clarity_score,
        "answer_completeness_score": completeness_score,
        "overall_score": overall,
        "feedback": "Solid response." if overall >= 7 else "Good start, but the answer needs more depth and structure.",
        "improvements": improvements or ["Add one measurable result to make the answer stronger."],
    }


async def next_question(role: str, level: str, interview_type: str, company: str, history: list[dict[str, str]], last_answer: str) -> dict[str, object]:
    score = score_answer(last_answer, role)
    llm_question = await _openai_question(role, level, interview_type, company, history, last_answer, score)
    if llm_question:
        question = llm_question
    else:
        question = _fallback_question(role, level, interview_type, company, history, last_answer, score)
    return {"agent": _agent_for_type(interview_type, len(history)), "question": question, "score": score}


def roadmap(scores: list[float], weak_topics: list[str]) -> list[str]:
    if not weak_topics:
        return []
    base = [
        "Practice one 20-minute mock interview daily and review the transcript.",
        "Rewrite weak answers using the STAR method and add measurable outcomes.",
        "Record two answers per week to improve pacing and clarity.",
    ]
    return [f"Spend focused practice on {topic}." for topic in weak_topics[:3]] + base


def _agent_for_type(interview_type: str, offset: int = 0) -> str:
    if interview_type == "Panel":
        return AGENTS[offset % len(AGENTS)]
    if interview_type == "HR":
        return "HR Interviewer"
    if interview_type == "Behavioral":
        return "Behavioral Interviewer"
    if interview_type == "Case Study":
        return "Manager Interviewer"
    return "Technical Interviewer"


def _technical_vocab(role: str) -> set[str]:
    words = {"api", "database", "sql", "python", "testing", "optimization", "model", "schema", "latency", "security"}
    for topic in ROLE_TOPICS.get(role, []):
        words.update(topic.lower().split())
    return words


def _fallback_question(role: str, level: str, interview_type: str, company: str, history: list[dict[str, str]], answer: str, score: dict[str, object]) -> str:
    topics = ROLE_TOPICS.get(role, ["problem solving", "communication"])
    asked = _normalize_questions(row["content"] for row in history if row.get("sender") == "AI")
    if score["technical_score"] < 7:
        return _pick_unasked(
            [
                f"Can you go deeper technically: what trade-offs or edge cases would matter for {topic}?"
                for topic in topics
            ]
            + [
                f"What would break first if this {role} solution had to scale for a real {company} project?",
                "Which assumption in your answer is riskiest, and how would you validate it?",
            ],
            asked,
        )
    if "pandas" in answer.lower():
        return "Why did you choose Pandas instead of SQL, and how did you handle missing values?"
    if "random forest" in answer.lower():
        return "Why Random Forest instead of Logistic Regression, and how did you validate the model?"
    if interview_type == "Behavioral":
        return _pick_unasked(
            [
                "Tell me about a time this approach failed. What did you change afterward?",
                "Give me a STAR example where you had to influence someone without authority.",
                "Describe a conflict in a team project and how you handled the outcome.",
            ],
            asked,
        )
    if interview_type == "Case Study":
        return _pick_unasked(
            [
                "Which KPIs would you check first, and how would you separate correlation from causation?",
                "What segmentation would you use first, and what decision would each segment support?",
                "How would you present the root cause if the data is incomplete or noisy?",
            ],
            asked,
        )
    return _pick_unasked(
        [
            f"Good. Now solve this at a {level.lower()} depth: how would you improve {topic} in a real {company} project?"
            for topic in topics
        ]
        + [
            f"How would you test whether your {role} solution is actually successful?",
            "What would you do differently if you had only one day to deliver the first version?",
        ],
        asked,
    )


async def _openai_question(role: str, level: str, interview_type: str, company: str, history: list[dict[str, str]], answer: str, score: dict[str, object]) -> str | None:
    if not os.getenv("OPENAI_API_KEY"):
        return None
    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI()
        messages = [
            {
                "role": "system",
                "content": "You are an expert interview simulator. Ask one concise, realistic follow-up question that has not already appeared in the recent history. Do not include feedback.",
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "role": role,
                        "level": level,
                        "type": interview_type,
                        "company": company,
                        "recent_history": history[-8:],
                        "last_answer": answer,
                        "score": score,
                    }
                ),
            },
        ]
        response = await client.chat.completions.create(model="gpt-4o-mini", messages=messages, temperature=0.8)
        return response.choices[0].message.content.strip()
    except Exception:
        return None


def _normalize_questions(questions) -> set[str]:
    return {_question_key(question) for question in questions if question}


def _pick_unasked(candidates: list[str], asked: set[str]) -> str:
    unseen = [question for question in candidates if question and _question_key(question) not in asked]
    return random.choice(unseen or candidates)


def _question_key(question: str) -> str:
    text = re.sub(r"\s+", " ", str(question).strip().lower())
    return re.sub(r"^[a-z0-9 &.-]+ style:\s*", "", text)
