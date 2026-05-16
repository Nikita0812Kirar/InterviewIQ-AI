import contextlib
import io
import json
import subprocess
import sys
import tempfile
from pathlib import Path


PROBLEMS = [
    {
        "title": "Two Sum",
        "difficulty": "Beginner",
        "prompt": "Write a function solve(nums, target) that returns indices of two numbers adding to target.",
        "starter": "def solve(nums, target):\n    return []\n",
        "tests": [
            {"input": [[2, 7, 11, 15], 9], "expected": [0, 1]},
            {"input": [[3, 2, 4], 6], "expected": [1, 2]},
        ],
    },
    {
        "title": "Valid Parentheses",
        "difficulty": "Beginner",
        "prompt": "Write a function solve(s) that returns true when every bracket is correctly closed and nested.",
        "starter": "def solve(s):\n    return False\n",
        "tests": [
            {"input": ["()[]{}"], "expected": True},
            {"input": ["([)]"], "expected": False},
            {"input": ["{[]}"], "expected": True},
        ],
    },
    {
        "title": "Palindrome Cleanup",
        "difficulty": "Beginner",
        "prompt": "Write a function solve(text) that ignores spaces, punctuation, and case while checking for a palindrome.",
        "starter": "def solve(text):\n    return False\n",
        "tests": [
            {"input": ["A man, a plan, a canal: Panama"], "expected": True},
            {"input": ["interview"], "expected": False},
        ],
    },
    {
        "title": "FizzBuzz List",
        "difficulty": "Beginner",
        "prompt": "Write a function solve(n) that returns the classic FizzBuzz values from 1 through n.",
        "starter": "def solve(n):\n    return []\n",
        "tests": [
            {"input": [5], "expected": ["1", "2", "Fizz", "4", "Buzz"]},
            {"input": [15], "expected": ["1", "2", "Fizz", "4", "Buzz", "Fizz", "7", "8", "Fizz", "Buzz", "11", "Fizz", "13", "14", "FizzBuzz"]},
        ],
    },
    {
        "title": "Word Frequency",
        "difficulty": "Intermediate",
        "prompt": "Write a function solve(words) that returns a dictionary with the count of each word.",
        "starter": "def solve(words):\n    return {}\n",
        "tests": [
            {"input": [["sql", "python", "sql", "api"]], "expected": {"sql": 2, "python": 1, "api": 1}},
            {"input": [["data", "data", "model"]], "expected": {"data": 2, "model": 1}},
        ],
    },
    {
        "title": "Top K Frequent",
        "difficulty": "Intermediate",
        "prompt": "Write a function solve(nums, k) that returns the k most frequent numbers. Break ties by smaller number first.",
        "starter": "def solve(nums, k):\n    return []\n",
        "tests": [
            {"input": [[1, 1, 1, 2, 2, 3], 2], "expected": [1, 2]},
            {"input": [[4, 4, 1, 1, 2, 2], 2], "expected": [1, 2]},
        ],
    },
    {
        "title": "SQL Revenue Ranking",
        "difficulty": "Intermediate",
        "prompt": "Given sales(region, rep, revenue), write SQL to rank reps by revenue inside each region.",
        "starter": "SELECT region, rep, revenue,\n       RANK() OVER (PARTITION BY region ORDER BY revenue DESC) AS revenue_rank\nFROM sales;",
        "tests": [],
    },
    {
        "title": "SQL Repeat Customers",
        "difficulty": "Intermediate",
        "prompt": "Given orders(customer_id, order_date, amount), write SQL to find customers with at least two orders.",
        "starter": "SELECT customer_id\nFROM orders\nGROUP BY customer_id\nHAVING COUNT(*) >= 2;",
        "tests": [],
    },
    {
        "title": "JavaScript Unique Emails",
        "difficulty": "Beginner",
        "prompt": "Write a function solve(emails) that returns unique email addresses in their original order.",
        "starter": "function solve(emails) {\n  return [];\n}",
        "tests": [],
    },
]


def evaluate_code(language: str, code: str, problem_title: str) -> dict[str, object]:
    if language.lower() == "python":
        return _run_python(code, problem_title)
    review = "Review-only mode for this language. Check correctness, complexity, readability, and edge cases."
    return {"passed": 0, "total": 0, "status": "review", "output": review, "ai_review": _review_code(code, language)}


def _run_python(code: str, problem_title: str) -> dict[str, object]:
    problem = next((item for item in PROBLEMS if item["title"] == problem_title), PROBLEMS[0])
    if not problem["tests"]:
        review = "This challenge is review-only for Python because it does not include executable Python tests."
        return {"passed": 0, "total": 0, "status": "review", "output": review, "ai_review": _review_code(code, "Python")}
    test_code = "\n".join(
        [
            code,
            "import json",
            "results=[]",
            *[
                f"results.append(solve(*{json.dumps(test['input'])}) == {json.dumps(test['expected'])})"
                for test in problem["tests"]
            ],
            "print(json.dumps(results))",
        ]
    )
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "submission.py"
        path.write_text(test_code, encoding="utf-8")
        try:
            proc = subprocess.run([sys.executable, str(path)], capture_output=True, text=True, timeout=5)
            if proc.returncode != 0:
                return {"passed": 0, "total": len(problem["tests"]), "status": "error", "output": proc.stderr[-1000:], "ai_review": _review_code(code, "Python")}
            results = json.loads(proc.stdout.strip() or "[]")
            return {
                "passed": sum(1 for item in results if item),
                "total": len(results),
                "status": "passed" if all(results) else "failed",
                "output": proc.stdout.strip(),
                "ai_review": _review_code(code, "Python"),
            }
        except Exception as exc:
            return {"passed": 0, "total": len(problem["tests"]), "status": "error", "output": str(exc), "ai_review": _review_code(code, "Python")}


def _review_code(code: str, language: str) -> str:
    notes = []
    if len(code.splitlines()) < 3:
        notes.append("Implementation looks too short; explain edge cases and return behavior.")
    if "for " in code or "while " in code:
        notes.append("Mention time complexity and why the loop is acceptable.")
    if language.lower() == "sql" and "over" in code.lower():
        notes.append("Good use of window functions for ranking-style questions.")
    return " ".join(notes) or "Readable solution. Add complexity analysis and edge-case handling in the interview."
