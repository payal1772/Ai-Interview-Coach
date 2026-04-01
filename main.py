import os
import mimetypes
import json
import sys
import ast
import tempfile
import subprocess
import shutil
import socket
import time
import urllib.request
import urllib.error
from datetime import timedelta
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from dotenv import load_dotenv
from PyPDF2 import PdfReader

load_dotenv()

mimetypes.add_type('application/javascript', '.js')

app = Flask(__name__)

# --- CONFIGURATION ---
app.config.update(
    UPLOAD_FOLDER='uploads',
    SECRET_KEY=os.getenv("SECRET_KEY", "dev_secret_key_998877"),
    SESSION_PERMANENT=False,
    PERMANENT_SESSION_LIFETIME=timedelta(minutes=30),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    MAX_CONTENT_LENGTH=5 * 1024 * 1024 
)

# --- AI Configuration ---
GEMINI_API_KEY = os.getenv("GOOGLE_API_KEY")
GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_TIMEOUT_SECONDS = int(os.getenv("GEMINI_TIMEOUT_SECONDS", "90"))
GEMINI_MAX_RETRIES = int(os.getenv("GEMINI_MAX_RETRIES", "2"))

LANGUAGE_CONFIG = {
    "python": {
        "label": "Python",
        "runtime": sys.executable,
    },
    "javascript": {
        "label": "JavaScript",
        "runtime": shutil.which("node"),
    },
    "java": {
        "label": "Java",
        "runtime": shutil.which("java"),
        "compiler": shutil.which("javac"),
    },
}

AVAILABLE_LANGUAGE_IDS = [
    language_id for language_id, config in LANGUAGE_CONFIG.items()
    if config.get("runtime") and (language_id != "java" or config.get("compiler"))
]

def generate_gemini_text(prompt):
    """Call Gemini directly over HTTP to avoid SDK/runtime compatibility issues."""
    if not GEMINI_API_KEY:
        raise RuntimeError("GOOGLE_API_KEY is not set. Add it to your .env file.")

    endpoint = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    )
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ]
    }
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    raw = None
    last_error = None
    for attempt in range(1, GEMINI_MAX_RETRIES + 1):
        try:
            with urllib.request.urlopen(request, timeout=GEMINI_TIMEOUT_SECONDS) as response:
                raw = json.loads(response.read().decode("utf-8"))
                break
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Gemini API request failed: {exc.code} {error_body}") from exc
        except (urllib.error.URLError, TimeoutError, socket.timeout) as exc:
            last_error = exc
            if attempt == GEMINI_MAX_RETRIES:
                reason = getattr(exc, "reason", None) or str(exc)
                raise RuntimeError(
                    "The AI service took too long to respond. Please try again in a moment."
                ) from exc
            time.sleep(min(2 * attempt, 4))

    if raw is None and last_error:
        raise RuntimeError("The AI service did not return a valid response. Please try again.")

    candidates = raw.get("candidates") or []
    if not candidates:
        raise RuntimeError(f"Gemini API returned no candidates: {raw}")

    parts = (candidates[0].get("content") or {}).get("parts") or []
    text = "".join(part.get("text", "") for part in parts if isinstance(part, dict)).strip()
    if not text:
        raise RuntimeError(f"Gemini API returned an empty response: {raw}")
    return text

def infer_candidate_languages(resume_text, job_desc, job_role):
    """Infer likely known languages from resume/JD, limited to locally supported runtimes."""
    combined = f"{resume_text}\n{job_desc}\n{job_role}".lower()
    matches = []
    keyword_map = {
        "python": ["python", "django", "flask", "fastapi", "pandas"],
        "javascript": ["javascript", "js", "node", "react", "express", "frontend"],
        "java": ["java", "spring", "spring boot", "jvm"],
    }
    for language_id, keywords in keyword_map.items():
        if language_id not in AVAILABLE_LANGUAGE_IDS:
            continue
        if any(keyword in combined for keyword in keywords):
            matches.append(language_id)

    if not matches:
        matches = AVAILABLE_LANGUAGE_IDS[:]

    return matches[:3]

def clean_json_response(raw_text):
    """Strip common markdown fences from model output before JSON parsing."""
    text = raw_text.strip()
    if text.startswith("```json"):
        text = text[len("```json"):].strip()
    elif text.startswith("```"):
        text = text[3:].strip()
    if text.endswith("```"):
        text = text[:-3].strip()
    return text

def validate_generation_inputs(job_desc, resume_file):
    """Require both JD text and a PDF resume before generating interview content."""
    cleaned_job_desc = (job_desc or "").strip()
    if not cleaned_job_desc:
        return "Please upload a resume and add the job description before generating questions or coding tests."

    if not resume_file or not resume_file.filename:
        return "Please upload a resume and add the job description before generating questions or coding tests."

    if not resume_file.filename.lower().endswith(".pdf"):
        return "Resume must be uploaded as a PDF file."

    return None

def clamp_score(value, minimum=0, maximum=10):
    try:
        return max(minimum, min(maximum, float(value)))
    except (TypeError, ValueError):
        return float(minimum)

def summarize_coding_results(coding_results):
    """Turn raw coding attempt data into compact metrics for scoring and reporting."""
    normalized = []
    for idx, item in enumerate(coding_results or [], start=1):
        total_tests = int(item.get("total_tests") or 0)
        passed_tests = int(item.get("passed_tests") or 0)
        passed_ratio = (passed_tests / total_tests) if total_tests else 0.0
        normalized.append({
            "title": (item.get("title") or f"Coding Challenge {idx}").strip(),
            "language": (item.get("language") or "python").lower(),
            "accepted": bool(item.get("accepted")),
            "passed_tests": passed_tests,
            "total_tests": total_tests,
            "passed_ratio": round(passed_ratio, 2),
            "quality_feedback": (item.get("quality_feedback") or "").strip(),
            "status": (item.get("status") or "").strip(),
        })

    attempted = len(normalized)
    accepted_count = sum(1 for item in normalized if item["accepted"])
    average_pass_ratio = round(
        sum(item["passed_ratio"] for item in normalized) / attempted,
        2
    ) if attempted else 0.0

    return {
        "attempted": attempted,
        "accepted_count": accepted_count,
        "average_pass_ratio": average_pass_ratio,
        "items": normalized
    }

def build_fallback_practice_report(voice_entries, coding_summary):
    """Create a deterministic report if the model response is unavailable."""
    answered_count = sum(
        1 for item in voice_entries
        if (item.get("answer") or "").strip() and "skipped" not in (item.get("answer") or "").lower()
    )
    total_questions = len(voice_entries)
    voice_completion = (answered_count / total_questions) if total_questions else 0.0

    coding_attempted = coding_summary.get("attempted", 0)
    coding_acceptance = (
        coding_summary.get("accepted_count", 0) / coding_attempted
        if coding_attempted else 0.0
    )
    coding_pass_ratio = coding_summary.get("average_pass_ratio", 0.0)

    technical = round((coding_pass_ratio * 6) + (voice_completion * 4), 1)
    communication = round(4 + (voice_completion * 6), 1)
    confidence = round(4 + (voice_completion * 5), 1)
    problem_solving = round((coding_acceptance * 5) + (coding_pass_ratio * 5), 1)
    code_quality = round((coding_pass_ratio * 7) + (coding_acceptance * 3), 1)
    overall = round((technical + communication + confidence + problem_solving + code_quality) / 5, 1)

    strengths = [
        "Completed the guided practice flow and stayed engaged across the round.",
        "Showed enough signal for technical and communication feedback."
    ]
    if coding_attempted and coding_summary.get("accepted_count", 0):
        strengths.append("Solved at least one coding task successfully under interview-style constraints.")

    improvements = [
        "Add more structure to spoken answers with concise examples and tradeoffs.",
        "Practice coding with explicit edge-case checks before final submission."
    ]
    if not coding_attempted:
        improvements.append("Attempt the coding round as part of the full practice flow for a stronger assessment.")

    recommendations = [
        "Use STAR for voice responses: situation, task, action, result.",
        "Before running code, test one normal case and one edge case mentally.",
        "Explain assumptions out loud while solving to improve interviewer confidence."
    ]

    return {
        "candidate_name": session.get("user_name", "Candidate"),
        "overview": {
            "title": "Practice Performance Report",
            "summary": "This report combines the voice mock interview and coding round into one readiness snapshot."
        },
        "scores": {
            "technical": technical,
            "communication": communication,
            "confidence": confidence,
            "problem_solving": problem_solving,
            "code_quality": code_quality,
            "overall": overall
        },
        "practice_summary": {
            "voice_questions": total_questions,
            "voice_answered": answered_count,
            "coding_attempted": coding_attempted,
            "coding_accepted": coding_summary.get("accepted_count", 0),
            "coding_pass_ratio": round(coding_pass_ratio * 100, 1)
        },
        "strengths": strengths[:4],
        "improvements": improvements[:4],
        "recommendations": recommendations[:4],
        "chart_series": {
            "score_labels": ["Technical", "Communication", "Confidence", "Problem Solving", "Code Quality"],
            "score_values": [technical, communication, confidence, problem_solving, code_quality],
            "practice_breakdown": [
                {"label": "Voice Completed", "value": answered_count},
                {"label": "Voice Remaining", "value": max(0, total_questions - answered_count)},
                {"label": "Coding Accepted", "value": coding_summary.get("accepted_count", 0)},
                {"label": "Coding Not Accepted", "value": max(0, coding_attempted - coding_summary.get("accepted_count", 0))}
            ]
        }
    }

def normalize_practice_report(raw_report, voice_entries, coding_summary):
    """Ensure the performance page always receives a predictable JSON structure."""
    fallback = build_fallback_practice_report(voice_entries, coding_summary)
    report = raw_report if isinstance(raw_report, dict) else {}

    fallback_scores = fallback["scores"]
    raw_scores = report.get("scores") if isinstance(report.get("scores"), dict) else {}
    scores = {
        "technical": round(clamp_score(raw_scores.get("technical", fallback_scores["technical"])), 1),
        "communication": round(clamp_score(raw_scores.get("communication", fallback_scores["communication"])), 1),
        "confidence": round(clamp_score(raw_scores.get("confidence", fallback_scores["confidence"])), 1),
        "problem_solving": round(clamp_score(raw_scores.get("problem_solving", fallback_scores["problem_solving"])), 1),
        "code_quality": round(clamp_score(raw_scores.get("code_quality", fallback_scores["code_quality"])), 1),
        "overall": round(clamp_score(raw_scores.get("overall", fallback_scores["overall"])), 1),
    }

    practice_summary = report.get("practice_summary") if isinstance(report.get("practice_summary"), dict) else {}
    fallback_summary = fallback["practice_summary"]

    normalized = {
        "candidate_name": (report.get("candidate_name") or fallback["candidate_name"]).strip(),
        "overview": {
            "title": ((report.get("overview") or {}).get("title") or fallback["overview"]["title"]).strip(),
            "summary": ((report.get("overview") or {}).get("summary") or fallback["overview"]["summary"]).strip(),
        },
        "scores": scores,
        "practice_summary": {
            "voice_questions": int(practice_summary.get("voice_questions", fallback_summary["voice_questions"])),
            "voice_answered": int(practice_summary.get("voice_answered", fallback_summary["voice_answered"])),
            "coding_attempted": int(practice_summary.get("coding_attempted", fallback_summary["coding_attempted"])),
            "coding_accepted": int(practice_summary.get("coding_accepted", fallback_summary["coding_accepted"])),
            "coding_pass_ratio": float(practice_summary.get("coding_pass_ratio", fallback_summary["coding_pass_ratio"])),
        },
        "strengths": [str(item).strip() for item in (report.get("strengths") or fallback["strengths"]) if str(item).strip()][:5],
        "improvements": [str(item).strip() for item in (report.get("improvements") or fallback["improvements"]) if str(item).strip()][:5],
        "recommendations": [str(item).strip() for item in (report.get("recommendations") or fallback["recommendations"]) if str(item).strip()][:5],
    }

    normalized["chart_series"] = {
        "score_labels": ["Technical", "Communication", "Confidence", "Problem Solving", "Code Quality"],
        "score_values": [
            normalized["scores"]["technical"],
            normalized["scores"]["communication"],
            normalized["scores"]["confidence"],
            normalized["scores"]["problem_solving"],
            normalized["scores"]["code_quality"],
        ],
        "practice_breakdown": [
            {"label": "Voice Answered", "value": normalized["practice_summary"]["voice_answered"]},
            {
                "label": "Voice Skipped",
                "value": max(0, normalized["practice_summary"]["voice_questions"] - normalized["practice_summary"]["voice_answered"])
            },
            {"label": "Coding Accepted", "value": normalized["practice_summary"]["coding_accepted"]},
            {
                "label": "Coding Needs Work",
                "value": max(0, normalized["practice_summary"]["coding_attempted"] - normalized["practice_summary"]["coding_accepted"])
            }
        ]
    }

    return normalized

def extract_text_from_pdf(pdf_file):
    """Utility to extract text from an uploaded PDF file safely."""
    text = ""
    try:
        if not pdf_file or pdf_file.filename == '':
            return "No resume provided."
        pdf_reader = PdfReader(pdf_file)
        for page in pdf_reader.pages:
            content = page.extract_text()
            if content:
                text += content
        return text.strip() if text else "PDF was empty or unreadable."
    except Exception as e:
        print(f"PDF Error: {e}")
        return "Error reading PDF."

def normalize_generated_content(data):
    """Ensure frontend gets a predictable structure even if the model is inconsistent."""
    interview_questions = []
    for item in data.get("interview_questions", []):
        question = (item.get("question") or "").strip()
        ideal_answer = (item.get("ideal_answer") or "").strip()
        if question and is_voice_safe_question(question):
            interview_questions.append({
                "question": question,
                "ideal_answer": ideal_answer or "No ideal answer provided."
            })

    coding_challenges = []
    for item in data.get("coding_challenges", []):
        title = (item.get("title") or "Coding Challenge").strip()
        prompt = (item.get("prompt") or "").strip()
        supported_languages = [
            language_id for language_id in (item.get("supported_languages") or [])
            if language_id in AVAILABLE_LANGUAGE_IDS
        ]
        if not supported_languages:
            supported_languages = AVAILABLE_LANGUAGE_IDS[:1] or ["python"]

        starter_code_by_language = item.get("starter_code_by_language") or {}
        normalized_starters = {}
        fallback_starters = {
            "python": (
                "import sys\n\n"
                "def solve():\n"
                "    data = sys.stdin.read().strip()\n"
                "    # Write your solution here\n"
                "    print(data)\n\n"
                "if __name__ == '__main__':\n"
                "    solve()\n"
            ),
            "javascript": (
                "const fs = require('fs');\n"
                "const input = fs.readFileSync(0, 'utf8').trim();\n"
                "// Write your solution here\n"
                "console.log(input);\n"
            ),
            "java": (
                "import java.io.*;\n"
                "import java.util.*;\n\n"
                "public class Main {\n"
                "    public static void main(String[] args) throws Exception {\n"
                "        BufferedReader br = new BufferedReader(new InputStreamReader(System.in));\n"
                "        String input = br.lines().reduce(\"\", (a, b) -> a + (a.isEmpty() ? \"\" : \"\\n\") + b).trim();\n"
                "        // Write your solution here\n"
                "        System.out.println(input);\n"
                "    }\n"
                "}\n"
            ),
        }

        for language_id in supported_languages:
            normalized_starters[language_id] = (
                starter_code_by_language.get(language_id)
                or fallback_starters.get(language_id, "")
            )

        if prompt:
            coding_challenges.append({
                "title": title,
                "prompt": prompt,
                "requirements": item.get("requirements") or [],
                "example_input": item.get("example_input") or "",
                "example_output": item.get("example_output") or "",
                "suggestion": (item.get("suggestion") or "Break the problem into input parsing, core logic, and output formatting. Validate edge cases before finalizing your answer.").strip(),
                "reference_answer_by_language": item.get("reference_answer_by_language") or {},
                "supported_languages": supported_languages,
                "starter_code_by_language": normalized_starters,
                "test_cases": [
                    {
                        "stdin": case.get("stdin", ""),
                        "expected_output": case.get("expected_output", "")
                    }
                    for case in (item.get("test_cases") or [])
                    if case.get("expected_output") is not None
                ]
            })

    return {
        "interview_questions": interview_questions,
        "coding_challenges": coding_challenges,
        "available_languages": AVAILABLE_LANGUAGE_IDS
    }

def is_voice_safe_question(question_text):
    """Filter out prompts that are better suited for a coding editor than a spoken answer."""
    text = question_text.lower()
    blocked_phrases = [
        "write code",
        "write a function",
        "implement",
        "code a",
        "coding challenge",
        "leetcode",
        "return the output",
        "time complexity of your code",
        "space complexity of your code",
        "pseudocode",
        "syntax",
        "compile",
        "program that",
        "debug this code",
        "fix the code",
        "complete the code",
        "write a program",
    ]
    return not any(phrase in text for phrase in blocked_phrases)

def build_code_runner(user_code, stdin_data, test_cases):
    """Create a wrapper that can evaluate print-based or function-return solutions."""
    return f"""
import ast
import contextlib
import io
import json
import traceback

USER_CODE = {user_code!r}
STDIN_DATA = {stdin_data!r}
TEST_CASES = {test_cases!r}

def parse_argument(raw_value, annotation_name):
    if isinstance(raw_value, str):
        raw_value = raw_value.strip()

    if annotation_name == 'str':
        return raw_value if isinstance(raw_value, str) else str(raw_value)
    if annotation_name == 'int':
        return raw_value if isinstance(raw_value, int) else int(raw_value)
    if annotation_name == 'float':
        return raw_value if isinstance(raw_value, float) else float(raw_value)
    if annotation_name == 'bool':
        if isinstance(raw_value, bool):
            return raw_value
        return str(raw_value).lower() in ('true', '1', 'yes')
    if annotation_name == 'list':
        if isinstance(raw_value, list):
            return raw_value
        if isinstance(raw_value, tuple):
            return list(raw_value)
        try:
            parsed = ast.literal_eval(raw_value) if isinstance(raw_value, str) else raw_value
            if isinstance(parsed, tuple):
                return list(parsed)
            return parsed
        except Exception:
            return raw_value.split() if isinstance(raw_value, str) else raw_value

    if isinstance(raw_value, str):
        try:
            return ast.literal_eval(raw_value)
        except Exception:
            return raw_value
    return raw_value

def prepare_arguments(function_node, stdin_text):
    cleaned = stdin_text.strip('\\n')
    params = function_node.args.args
    if not params:
        return []

    lines = cleaned.splitlines() if cleaned else []
    literal_block = None
    if cleaned:
        try:
            literal_block = ast.literal_eval(cleaned)
        except Exception:
            literal_block = None

    if len(params) == 1:
        annotation_name = getattr(function_node.args.args[0].annotation, 'id', None)
        if annotation_name == 'str':
            return [cleaned]
        source_value = literal_block if literal_block is not None else cleaned
        return [parse_argument(source_value, annotation_name)]

    if isinstance(literal_block, tuple) and len(literal_block) == len(params):
        raw_parts = list(literal_block)
    elif isinstance(literal_block, list) and len(literal_block) == len(params):
        raw_parts = list(literal_block)
    elif len(lines) == len(params):
        raw_parts = lines
    else:
        raw_parts = cleaned.split()
        if len(raw_parts) == 1 and literal_block is not None and isinstance(literal_block, (list, tuple)):
            raw_parts = list(literal_block)

    raw_parts += [''] * max(0, len(params) - len(raw_parts))

    values = []
    for idx, param in enumerate(params):
        annotation_name = getattr(param.annotation, 'id', None)
        values.append(parse_argument(raw_parts[idx], annotation_name))
    return values

namespace = {{}}
result_payload = {{
    "stdout": "",
    "stderr": "",
    "returncode": 0,
    "function_result": "",
    "passed_all_tests": False,
    "passed_count": 0,
    "total_tests": 0,
    "failed_case": None
}}

def normalize_output(value):
    return str(value if value is not None else '').replace('\\r\\n', '\\n').strip()

def execute_candidate(stdin_text):
    namespace = {{}}
    captured = io.StringIO()
    tree = ast.parse(USER_CODE)
    function_nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef)]

    with contextlib.redirect_stdout(captured):
        exec(compile(USER_CODE, '<candidate_code>', 'exec'), namespace)

        if not captured.getvalue().strip() and function_nodes:
            target = function_nodes[0]
            fn = namespace.get(target.name)
            if callable(fn):
                arguments = prepare_arguments(target, stdin_text)
                returned = fn(*arguments)
                if returned is not None:
                    print(returned)
                    return captured.getvalue(), "", 0, str(returned)

    return captured.getvalue(), "", 0, ""

try:
    stdout, stderr, returncode, function_result = execute_candidate(STDIN_DATA)
    result_payload["stdout"] = stdout
    result_payload["stderr"] = stderr
    result_payload["returncode"] = returncode
    result_payload["function_result"] = function_result

    if TEST_CASES:
        passed_count = 0
        failed_case = None
        for index, case in enumerate(TEST_CASES, start=1):
            case_stdout, case_stderr, case_returncode, _ = execute_candidate(case.get("stdin", ""))
            expected = normalize_output(case.get("expected_output", ""))
            actual = normalize_output(case_stdout)

            if case_returncode == 0 and not case_stderr and actual == expected:
                passed_count += 1
            elif failed_case is None:
                failed_case = {{
                    "index": index,
                    "expected_output": expected,
                    "actual_output": actual,
                    "stdin": case.get("stdin", "")
                }}

        result_payload["passed_count"] = passed_count
        result_payload["total_tests"] = len(TEST_CASES)
        result_payload["passed_all_tests"] = passed_count == len(TEST_CASES)
        result_payload["failed_case"] = failed_case
    else:
        result_payload["passed_all_tests"] = True
        result_payload["passed_count"] = 0
        result_payload["total_tests"] = 0
except Exception:
    result_payload["returncode"] = 1
    result_payload["stderr"] = traceback.format_exc()

print(json.dumps(result_payload))
"""

def normalize_output_text(value):
    text = str(value if value is not None else "").replace("\r\n", "\n").strip()
    lowered = text.lower()
    literal_map = {
        "true": "true",
        "false": "false",
        "none": "null",
        "null": "null",
    }
    return literal_map.get(lowered, text)

def assess_code_quality(code, language):
    """Return lightweight code-quality feedback without blocking acceptance."""
    text = code or ""
    lines = [line for line in text.splitlines() if line.strip()]
    notes = []

    if len(lines) <= 3:
        notes.append("The solution is very short; consider making the logic easier to follow if this were production code.")
    if "print(" in text and language == "python" and "def " not in text:
        notes.append("The answer works as a script, though wrapping logic in a function would improve structure.")
    if language == "python" and "import *" in text:
        notes.append("Avoid wildcard imports to keep dependencies explicit.")
    if language == "javascript" and "var " in text:
        notes.append("Prefer let/const over var for clearer scoping.")
    if language == "java" and "class Main" not in text:
        notes.append("Java submissions should keep a clear Main entrypoint for interview-style execution.")
    if len(lines) > 20 and not any("#" in line or "//" in line for line in lines):
        notes.append("A brief comment on the core idea could improve readability in a collaborative setting.")

    if not notes:
        notes.append("The solution is clear and appropriately scoped for an interview-style answer.")

    return " ".join(notes)

def run_subprocess(command, stdin_data="", cwd=None, timeout=5):
    return subprocess.run(
        command,
        input=stdin_data,
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=cwd
    )

def execute_python_submission(code, stdin_data, test_cases):
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.py',
            delete=False,
            encoding='utf-8'
        ) as temp_file:
            temp_file.write(build_code_runner(code, stdin_data, test_cases))
            temp_path = temp_file.name

        completed = run_subprocess([sys.executable, temp_path], timeout=5)
        if completed.returncode != 0:
            return {
                "stdout": completed.stdout,
                "stderr": completed.stderr,
                "returncode": completed.returncode,
                "passed_all_tests": False,
                "passed_count": 0,
                "total_tests": len(test_cases),
                "failed_case": None,
            }

        runner_payload = json.loads(completed.stdout or "{}")
        return {
            "stdout": runner_payload.get("stdout", ""),
            "stderr": runner_payload.get("stderr", ""),
            "returncode": runner_payload.get("returncode", 0),
            "function_result": runner_payload.get("function_result", ""),
            "passed_all_tests": runner_payload.get("passed_all_tests", False),
            "passed_count": runner_payload.get("passed_count", 0),
            "total_tests": runner_payload.get("total_tests", 0),
            "failed_case": runner_payload.get("failed_case"),
        }
    finally:
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)

def judge_with_process(command_builder, code_filename, code, stdin_data, test_cases):
    temp_dir = tempfile.mkdtemp(prefix="coding_round_")
    try:
        code_path = os.path.join(temp_dir, code_filename)
        with open(code_path, "w", encoding="utf-8") as handle:
            handle.write(code)

        setup_result = command_builder("setup", temp_dir)
        if setup_result is not None and setup_result.returncode != 0:
            return {
                "stdout": setup_result.stdout,
                "stderr": setup_result.stderr,
                "returncode": setup_result.returncode,
                "passed_all_tests": False,
                "passed_count": 0,
                "total_tests": len(test_cases),
                "failed_case": None,
            }

        visible_run = command_builder("run", temp_dir, stdin_data)
        if visible_run.returncode != 0:
            return {
                "stdout": visible_run.stdout,
                "stderr": visible_run.stderr,
                "returncode": visible_run.returncode,
                "passed_all_tests": False,
                "passed_count": 0,
                "total_tests": len(test_cases),
                "failed_case": None,
            }

        passed_count = 0
        failed_case = None
        for index, case in enumerate(test_cases, start=1):
            case_run = command_builder("run", temp_dir, case.get("stdin", ""))
            expected = normalize_output_text(case.get("expected_output", ""))
            actual = normalize_output_text(case_run.stdout)
            if case_run.returncode == 0 and not case_run.stderr and actual == expected:
                passed_count += 1
            elif failed_case is None:
                failed_case = {
                    "index": index,
                    "expected_output": expected,
                    "actual_output": actual,
                    "stdin": case.get("stdin", "")
                }

        total_tests = len(test_cases)
        return {
            "stdout": visible_run.stdout,
            "stderr": visible_run.stderr,
            "returncode": visible_run.returncode,
            "passed_all_tests": passed_count == total_tests if total_tests else True,
            "passed_count": passed_count,
            "total_tests": total_tests,
            "failed_case": failed_case,
        }
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

def execute_javascript_submission(code, stdin_data, test_cases):
    def js_command(mode, temp_dir, run_stdin=""):
        if mode == "setup":
            return None
        return run_subprocess(
            [LANGUAGE_CONFIG["javascript"]["runtime"], "solution.js"],
            stdin_data=run_stdin,
            cwd=temp_dir,
            timeout=5
        )

    return judge_with_process(js_command, "solution.js", code, stdin_data, test_cases)

def execute_java_submission(code, stdin_data, test_cases):
    def java_command(mode, temp_dir, run_stdin=""):
        if mode == "setup":
            return run_subprocess(
                [LANGUAGE_CONFIG["java"]["compiler"], "Main.java"],
                cwd=temp_dir,
                timeout=10
            )
        return run_subprocess(
            [LANGUAGE_CONFIG["java"]["runtime"], "Main"],
            stdin_data=run_stdin,
            cwd=temp_dir,
            timeout=5
        )

    return judge_with_process(java_command, "Main.java", code, stdin_data, test_cases)

# --- AUTH & SESSION ROUTES ---

@app.route('/')
def auth_page():
    if session.get('user_id'):
        return redirect(url_for('dashboard'))
    return render_template('auth.html')

@app.route('/auth')
def auth_alias():
    return redirect(url_for('auth_page'))

@app.route('/set_session', methods=['POST'])
def set_session():
    data = request.json
    session.permanent = False
    session['user_id'] = data.get('uid')
    session['role'] = data.get('role') # Crucial for dashboard logic
    session['user_name'] = data.get('displayName') or "User"
    return jsonify({"status": "success"})

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth_page'))

@app.route('/switch-account')
def switch_account():
    session.clear()
    return redirect(url_for('auth_page'))

@app.route('/dashboard')
def dashboard():
    if not session.get('user_id'):
        return redirect(url_for('auth_page'))
    return render_template('index.html', user_name=session.get('user_name', 'User'))

@app.route('/performance-report')
def performance_report():
    if not session.get('user_id'):
        return redirect(url_for('auth_page'))
    if not session.get('last_practice_report') and request.args.get('source') != 'history':
        return redirect(url_for('dashboard'))
    return render_template('performance_report.html', user_name=session.get('user_name', 'User'))

@app.route('/performance-report-data')
def performance_report_data():
    if not session.get('user_id'):
        return jsonify({"error": "Unauthorized"}), 401
    report = session.get('last_practice_report')
    if not report:
        return jsonify({"error": "No performance report available."}), 404
    return jsonify(report)

# --- UPDATED INTERVIEW LOGIC ---

# Inside main.py - update the /generate route prompt
@app.route('/generate', methods=['POST'])
def generate_questions():
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    try:
        job_role = request.form.get('job_role', 'Software Developer')
        difficulty = request.form.get('difficulty', 'Entry Level')
        num_questions = request.form.get('num_questions', '5')
        job_desc = request.form.get('job_description', '')
        q_type = request.form.get('q_type', 'technical')
        requested_count = max(1, min(int(num_questions), 10))
        resume_file = request.files.get('resume')

        validation_error = validate_generation_inputs(job_desc, resume_file)
        if validation_error:
            return jsonify({"error": validation_error}), 400

        category_instructions = {
            "technical": "Focus on CS fundamentals, problem-solving, debugging, and practical software engineering concepts.",
            "behavioral": "Focus on past experiences using the STAR method.",
            "situational": "Focus on hypothetical problem-solving.",
            "system_design": "Focus on architecture and scalability."
        }

        coding_count = 1 if q_type == "technical" else 0
        interview_count = max(1, requested_count - coding_count)
        resume_text = extract_text_from_pdf(resume_file)
        preferred_languages = infer_candidate_languages(resume_text, job_desc, job_role)

        coding_instructions = (
            f'Include exactly {coding_count} coding_challenges. '
            'Each coding challenge must be solvable in locally supported languages and include starter_code_by_language.'
            if coding_count else
            'Return an empty coding_challenges array.'
        )

        prompt = (
            "You are a senior interviewer and coding screener. "
            f"Generate content for a {difficulty} {job_role} candidate. "
            f"Question category focus: {q_type}. "
            f"Context: Job description: {job_desc}. Resume: {resume_text}. "
            f"{category_instructions.get(q_type, '')} "
            f"Return ONLY valid JSON with this exact shape: "
            "{"
            "\"interview_questions\": ["
            "{\"question\": \"...\", \"ideal_answer\": \"...\"}"
            "], "
            "\"coding_challenges\": ["
            "{"
            "\"title\": \"...\", "
            "\"prompt\": \"...\", "
            "\"requirements\": [\"...\"], "
            "\"example_input\": \"...\", "
            "\"example_output\": \"...\", "
            "\"suggestion\": \"...\", "
            "\"supported_languages\": [\"python\"], "
            "\"starter_code_by_language\": {\"python\": \"...\", \"javascript\": \"...\", \"java\": \"...\"}, "
            "\"reference_answer_by_language\": {\"python\": \"...\", \"javascript\": \"...\", \"java\": \"...\"}, "
            "\"test_cases\": [{\"stdin\": \"...\", \"expected_output\": \"...\"}]"
            "}"
            "]"
            "}. "
            f"Create exactly {interview_count} interview_questions. "
            "These interview_questions must be answerable fully using words and complete spoken sentences. "
            "Do not ask the candidate to write code, produce pseudocode, give syntax, or solve a live editor problem in interview_questions. "
            "If the category is technical, keep the questions conceptual, experience-based, design-oriented, debugging-oriented, or explanation-based so they work naturally in a voice interview. "
            f"{coding_instructions} "
            f"The coding round must reflect the candidate background from the resume and the job requirements from the JD. "
            f"Preferred languages based on the candidate profile: {', '.join(preferred_languages)}. "
            f"Locally runnable languages available in this environment: {', '.join(AVAILABLE_LANGUAGE_IDS)}. "
            "Choose 1 to 3 supported_languages for each coding challenge from the locally runnable set, prioritizing the candidate's likely known languages and the role stack. "
            "For every supported language, provide starter_code_by_language that reads from standard input and prints the final answer. "
            "Also provide a short suggestion and a correct reference_answer_by_language for each supported language. "
            "Each coding challenge must include 3 to 5 realistic test_cases for backend judging. "
            "Do not use markdown fences. Do not include extra commentary."
        )
        
        response_text = generate_gemini_text(prompt)
        payload = normalize_generated_content(json.loads(clean_json_response(response_text)))
        if not payload["interview_questions"]:
            payload["interview_questions"] = [{
                "question": f"Explain how you would approach core {job_role} responsibilities in this role and the tradeoffs you would consider.",
                "ideal_answer": "A strong answer explains a practical approach, references relevant experience, discusses tradeoffs clearly, and communicates decisions in a structured way."
            }]
        return jsonify(payload)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/evaluate_practice', methods=['POST'])
def evaluate_practice():
    if not session.get('user_id'):
        return jsonify({"error": "Unauthorized"}), 401

    payload = request.json or {}
    voice_entries = payload.get('voice_transcript') or []
    coding_results = payload.get('coding_results') or []
    coding_summary = summarize_coding_results(coding_results)

    if not voice_entries and not coding_summary.get("attempted"):
        return jsonify({"error": "No practice data submitted."}), 400

    transcript = "\n\n".join(
        f"Question: {item.get('question', '').strip()}\nAnswer: {item.get('answer', '').strip()}"
        for item in voice_entries
        if item.get('question')
    )

    coding_lines = []
    for item in coding_summary["items"]:
        coding_lines.append(
            f"Challenge: {item['title']}\n"
            f"Language: {item['language']}\n"
            f"Accepted: {item['accepted']}\n"
            f"Passed Tests: {item['passed_tests']}/{item['total_tests']}\n"
            f"Quality Feedback: {item['quality_feedback']}\n"
            f"Status: {item['status']}"
        )

    evaluation_prompt = f"""
You are an expert interview coach.
Analyze this combined mock interview practice made of a voice interview and a coding round.

Candidate name: {session.get('user_name', 'Candidate')}

Voice interview transcript:
{transcript or 'No voice interview answers were submitted.'}

Coding round summary:
{chr(10).join(coding_lines) if coding_lines else 'No coding attempts were submitted.'}

Return ONLY valid JSON in this exact structure:
{{
  "candidate_name": "Candidate",
  "overview": {{
    "title": "Practice Performance Report",
    "summary": "2 to 3 sentences summarizing readiness across voice interview and coding round."
  }},
  "scores": {{
    "technical": 0-10,
    "communication": 0-10,
    "confidence": 0-10,
    "problem_solving": 0-10,
    "code_quality": 0-10,
    "overall": 0-10
  }},
  "practice_summary": {{
    "voice_questions": {len(voice_entries)},
    "voice_answered": {sum(1 for item in voice_entries if (item.get('answer') or '').strip() and 'skipped' not in (item.get('answer') or '').lower())},
    "coding_attempted": {coding_summary['attempted']},
    "coding_accepted": {coding_summary['accepted_count']},
    "coding_pass_ratio": {round(coding_summary['average_pass_ratio'] * 100, 1)}
  }},
  "strengths": ["3 to 5 concise bullets"],
  "improvements": ["3 to 5 concise bullets"],
  "recommendations": ["3 to 5 concise next-step suggestions"]
}}
Do not use markdown fences.
"""

    try:
        response_text = generate_gemini_text(evaluation_prompt)
        json_text = response_text.strip().removeprefix('```json').removesuffix('```').strip()
        normalized_report = normalize_practice_report(json.loads(json_text), voice_entries, coding_summary)
    except Exception as e:
        print(f"Practice Evaluation Error: {e}")
        normalized_report = build_fallback_practice_report(voice_entries, coding_summary)

    session['last_practice_report'] = normalized_report
    return jsonify({
        "status": "success",
        "redirect_url": url_for('performance_report'),
        "report": normalized_report
    })

@app.route('/run_code', methods=['POST'])
def run_code():
    if not session.get('user_id'):
        return jsonify({"error": "Unauthorized"}), 401

    payload = request.json or {}
    code = (payload.get('code') or '').strip()
    stdin_data = payload.get('stdin') or ''
    test_cases = payload.get('test_cases') or []
    language = (payload.get('language') or 'python').lower()
    example_output = payload.get('example_output') or ''

    if not code:
        return jsonify({"error": "No code provided."}), 400
    if language not in AVAILABLE_LANGUAGE_IDS:
        return jsonify({"error": f"Language '{language}' is not supported on this server."}), 400

    try:
        if language == "python":
            result = execute_python_submission(code, stdin_data, test_cases)
        elif language == "javascript":
            result = execute_javascript_submission(code, stdin_data, test_cases)
        elif language == "java":
            result = execute_java_submission(code, stdin_data, test_cases)
        else:
            return jsonify({"error": f"Language '{language}' is not implemented."}), 400

        visible_output = normalize_output_text(result.get("stdout", ""))
        expected_visible_output = normalize_output_text(example_output)
        visible_match = bool(expected_visible_output) and visible_output == expected_visible_output
        accepted = visible_match or bool(result.get("passed_all_tests"))

        result["visible_match"] = visible_match
        result["accepted"] = accepted
        result["quality_feedback"] = assess_code_quality(code, language)

        return jsonify(result)
    except subprocess.TimeoutExpired:
        return jsonify({"error": "Code execution timed out after 5 seconds."}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    app.run(debug=True)
