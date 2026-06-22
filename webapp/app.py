#!/usr/bin/env python3
"""
app.py — Resume Builder Web App (F002)
Run: python webapp/app.py   (from project root, with .venv active)
Opens at: http://localhost:5000
"""

import json
import re
import sys
import threading
from datetime import datetime
from pathlib import Path

import requests as http
import yaml
from flask import Flask, Response, jsonify, render_template, request
from jinja2 import Environment, FileSystemLoader

ROOT        = Path(__file__).parent.parent
RESUME_DIR  = ROOT / "resume"
BASE_YAML   = RESUME_DIR / "resume-base.yaml"
TMPL_DIR    = Path(__file__).parent / "templates"
MEMORY_DIR  = Path(__file__).parent / "memory"
SESSIONS_DIR = MEMORY_DIR / "sessions"
FACTS_FILE  = MEMORY_DIR / "facts.json"
WORKLOG_FILE = MEMORY_DIR / "work_log.json"
PREFS_FILE  = MEMORY_DIR / "job_preferences.json"
sys.path.insert(0, str(RESUME_DIR))

app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = "dev-secret-key"

OLLAMA_URL   = "http://localhost:11434/api/chat"
OLLAMA_MODEL = "qwen3:32b"
AGENT_MODEL  = "Qwen3.5:27B"       # F003 tool-calling — separate from F002 coaching model

_stop_event = threading.Event()     # set by /api/agent/stop; cleared at start of each new chat

# ── Memory storage init ───────────────────────────────────────────────────────

def _init_memory_dirs():
    """Create memory directories and empty files on first run."""
    MEMORY_DIR.mkdir(exist_ok=True)
    SESSIONS_DIR.mkdir(exist_ok=True)
    if not FACTS_FILE.exists():
        FACTS_FILE.write_text(json.dumps({"updated": "", "facts": []}, indent=2))
    if not WORKLOG_FILE.exists():
        WORKLOG_FILE.write_text(json.dumps({"updated": "", "completed": [], "pending": []}, indent=2))
    if not PREFS_FILE.exists():
        PREFS_FILE.write_text(json.dumps({
            "titles": [], "location_types": [], "locations_onsite": [],
            "locations_remote": [], "employment_types": [],
            "experience_levels": [], "min_salary": 0,
        }, indent=2))

_init_memory_dirs()

# ── F003 — DB + scraper imports ───────────────────────────────────────────────

from db import init_db, insert_jobs, get_jobs, update_status, update_scores, export_csv
from scrapers import run_jobspy, run_himalayas, run_arbeitnow
init_db()

# ── Section definitions ───────────────────────────────────────────────────────

SECTIONS = [
    {
        'key': 'meta',
        'label': 'Contact Information',
        'intro': "Let's start with your contact details.",
        'questions': [
            ('name',           "What is your full name?"),
            ('location',       "What city and state are you in? (e.g. Portland, OR)"),
            ('phone',          "What is your phone number?"),
            ('email',          "What is your email address?"),
            ('linkedin_label', "What should your LinkedIn link say? (e.g. 'LinkedIn Profile')"),
            ('linkedin_url',   "What is your LinkedIn URL?"),
        ],
        'polish': False,
        'loop':   False,
    },
    {
        'key': 'title',
        'label': 'Professional Title',
        'intro': "Now let's craft your professional headline — this appears right below your name.",
        'questions': [
            ('raw', "What are your professional roles or titles? Separate multiple with | (e.g. 'Cloud Architect | Full Stack Developer')"),
        ],
        'polish': False,
        'loop':   False,
    },
    {
        'key': 'summary',
        'label': 'Career Summary',
        'intro': "Now for your career summary — a few paragraphs that introduce who you are. Don't worry about polish, just answer naturally.",
        'questions': [
            ('background', "Describe your professional background — what you do, your experience, and what you bring to the table."),
            ('current',    "What are you currently working on or studying?"),
            ('passion',    "What are you passionate about professionally, and what kind of opportunities are you looking for?"),
        ],
        'polish': True,
        'loop':   False,
    },
    {
        'key': 'expertise',
        'label': 'Areas of Expertise',
        'intro': "Let's capture your key areas of expertise. These appear as a two-column grid on your resume.",
        'questions': [
            ('raw', "List your main areas of expertise — technical skills, methodologies, and soft skills. Separate with commas or new lines."),
        ],
        'polish': True,
        'loop':   False,
    },
    {
        'key': 'experience',
        'label': 'Work Experience',
        'intro': "Now let's go through your work experience, starting with your most recent position.",
        'questions': [
            ('company',          "What is the company name?"),
            ('location',         "Where is the company located? (e.g. Portland, OR — or 'Remote')"),
            ('title',            "What was your job title?"),
            ('dates',            "What were the start and end dates? (e.g. '2022 – Present' or '2019 – 2022')"),
            ('responsibilities', "Describe your key responsibilities, projects, and achievements in this role. Be as detailed as you like."),
        ],
        'polish': True,
        'loop':   True,
        'loop_question': "Do you have another position to add? (yes / no)",
    },
    {
        'key': 'education',
        'label': 'Education',
        'intro': "Let's add your education, starting with your highest degree.",
        'questions': [
            ('degree',      "What is your degree? (e.g. 'M.S. in Computer Science')"),
            ('institution', "What is the name of the university or school?"),
            ('location',    "Where is it located? (city, state)"),
            ('year',        "What year did you graduate (or expect to)?"),
        ],
        'polish': False,
        'loop':   True,
        'loop_question': "Do you have another degree or education entry to add? (yes / no)",
    },
    {
        'key': 'certifications',
        'label': 'Certifications',
        'intro': "Let's add your certifications.",
        'questions': [
            ('raw', "List your certifications — include the name, issuer, and year for each. One per line or separated by commas."),
        ],
        'polish': True,
        'loop':   False,
    },
    {
        'key': 'skills',
        'label': 'Technical Skills',
        'intro': "Now let's capture your technical skills by category.",
        'questions': [
            ('raw', "List your technical skills, grouped by category if possible. Example: 'Cloud: AWS Lambda, S3; Languages: Python, JavaScript; Tools: Git, Docker'"),
        ],
        'polish': True,
        'loop':   False,
    },
    {
        'key': 'languages',
        'label': 'Languages',
        'intro': "Finally, what languages do you speak?",
        'questions': [
            ('raw', "List your languages and proficiency levels. (e.g. 'English – Native, Spanish – Conversational')"),
        ],
        'polish': False,
        'loop':   False,
    },
]

# ── In-memory session state ───────────────────────────────────────────────────

def fresh_state() -> dict:
    return {
        'section_idx':  0,
        'question_idx': 0,
        'answers':      {},   # field → answer for current section/loop item
        'loop_items':   [],   # collected items for loop sections
        'awaiting_loop_confirm': False,
        'loaded': False,      # True when resume was loaded vs built via Q&A
        'chat_history': [],   # coaching conversation history
        'session_file': None, # Path to current session JSONL log
        'resume_data':  {     # accumulates as sections complete
            'meta':           {'name': '', 'location': '', 'phone': '', 'email': '',
                               'linkedin_label': 'LinkedIn Profile', 'linkedin_url': ''},
            'title':          '',
            'summary':        [],
            'expertise':      [],
            'experience':     [],
            'education':      [],
            'certifications': [],
            'skills':         [],
            'languages':      '',
        },
    }

state: dict = fresh_state()
resume_state: dict = {}  # last loaded/built resume (for /load)

agent_state: dict = {
    "messages":        [],
    "search_criteria": {},
    "active_sources":  [],
    "search_done":     False,
}

# ── Ollama helpers ────────────────────────────────────────────────────────────

def call_ollama(messages: list, think: bool = False) -> str:
    """Call Ollama. think=False (default) skips Qwen3 reasoning chain for speed.
    think=True lets Qwen3 reason fully — better for coaching/analysis tasks."""
    msgs = list(messages)
    if "qwen3" in OLLAMA_MODEL.lower() and not think:
        # Disable reasoning chain for fast structured tasks (Q&A polish)
        if msgs and msgs[-1].get('role') == 'user':
            msgs[-1] = dict(msgs[-1])
            msgs[-1]['content'] = "/no_think\n" + msgs[-1]['content']
    try:
        r = http.post(OLLAMA_URL, json={'model': OLLAMA_MODEL, 'messages': msgs, 'stream': False}, timeout=180)
        r.raise_for_status()
        content = r.json()['message']['content'].strip()
        # Always strip <think>...</think> — user never needs to see raw reasoning
        content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()
        return content
    except Exception as e:
        return f"[Ollama error: {e}]"


def call_ollama_with_tools(messages: list, tools: list) -> tuple:
    """Call Ollama with tool definitions. Returns (content, tool_calls)."""
    try:
        r = http.post(OLLAMA_URL, json={"model": AGENT_MODEL, "messages": messages,
                                        "tools": tools, "stream": False}, timeout=180)
        r.raise_for_status()
        msg = r.json()["message"]
        content = msg.get("content") or ""
        if content:
            content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
        tool_calls = msg.get("tool_calls") or []
        return content, tool_calls
    except Exception as e:
        return f"[Agent error: {e}]", []


def _new_session_file() -> Path:
    """Return a new session log path with current timestamp."""
    return SESSIONS_DIR / f"{datetime.now().strftime('%Y-%m-%d_%H-%M')}.jsonl"


def log_turn(role: str, content: str) -> None:
    """Append one turn to the current session JSONL log."""
    if not state.get('session_file'):
        return
    entry = json.dumps({"role": role, "content": content, "ts": datetime.now().isoformat()})
    with open(state['session_file'], "a", encoding="utf-8") as f:
        f.write(entry + "\n")


def load_memory() -> dict:
    """Read facts.json and work_log.json; return combined dict. Returns empty structure on missing/corrupt files."""
    try:
        facts = json.loads(FACTS_FILE.read_text()) if FACTS_FILE.exists() else {}
    except Exception:
        facts = {}
    try:
        worklog = json.loads(WORKLOG_FILE.read_text()) if WORKLOG_FILE.exists() else {}
    except Exception:
        worklog = {}
    return {
        "facts":     facts.get("facts", []),
        "completed": worklog.get("completed", []),
        "pending":   worklog.get("pending", []),
    }


def format_memory_block(memory: dict) -> str:
    """Format the memory dict as the === MEMORY === prompt block. Returns '' if all lists empty."""
    facts     = memory.get("facts", [])
    pending   = memory.get("pending", [])
    completed = memory.get("completed", [])
    if not facts and not pending and not completed:
        return ""
    lines = ["=== MEMORY FROM PAST SESSIONS ==="]
    if facts:
        lines.append("Facts:")
        lines.extend(f"- {f}" for f in facts)
    if pending:
        lines.append("\nPending work:")
        lines.extend(f"- {p}" for p in pending)
    if completed:
        lines.append("\nRecently completed:")
        lines.extend(f"- {c}" for c in completed)
    lines.append("=== END MEMORY ===")
    return "\n".join(lines)


def save_memory(facts_list: list, worklog_dict: dict) -> None:
    """Atomic write: write to .tmp then rename to prevent corruption on interrupt."""
    today = datetime.now().strftime("%Y-%m-%d")
    facts_data   = {"updated": today, "facts": facts_list}
    worklog_data = {"updated": today, **worklog_dict}
    for path, data in [(FACTS_FILE, facts_data), (WORKLOG_FILE, worklog_data)]:
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        tmp.rename(path)


def _format_preferences() -> str:
    """Format saved job preferences as a structured search plan for the agent. Returns '' if nothing set."""
    try:
        prefs = json.loads(PREFS_FILE.read_text()) if PREFS_FILE.exists() else {}
    except Exception:
        return ""
    if not any([prefs.get("titles"), prefs.get("location_types"), prefs.get("employment_types"),
                prefs.get("experience_levels"), prefs.get("min_salary")]):
        return ""

    titles        = prefs.get("titles", [])
    loc_types     = prefs.get("location_types", [])   # ["onsite", "hybrid", "remote"]
    locs_onsite   = prefs.get("locations_onsite", [])
    locs_remote   = prefs.get("locations_remote", [])
    emp_types     = prefs.get("employment_types", [])
    exp_levels    = prefs.get("experience_levels", [])
    min_salary    = prefs.get("min_salary")

    type_map  = {"onsite": "On-site", "hybrid": "Hybrid", "remote": "Remote"}
    emp_map   = {"fulltime": "Full-time", "parttime": "Part-time",
                 "contract": "Contract", "internship": "Internship"}
    level_map = {"internship": "Internship", "entry": "Entry level", "associate": "Associate",
                 "mid_senior": "Mid-Senior", "director": "Director", "executive": "Executive"}

    # All selected location types apply to on-site location searches
    onsite_search_types = [type_map[t] for t in loc_types] if loc_types else []

    lines = ["=== JOB PREFERENCES ==="]

    if titles:
        lines.append(f"Job titles: {', '.join(titles)}")

    # ── On-site location searches ──────────────────────────────────────────────
    if locs_onsite:
        if onsite_search_types:
            lines.append(
                f"\nOn-site location searches — for each location below, search using ALL of these "
                f"selected job types: {', '.join(onsite_search_types)}. Use remote=False:"
            )
        else:
            lines.append("\nOn-site location searches — no location types selected, skip these:")
        for loc in locs_onsite:
            lines.append(f"  - {loc}")

    # ── Remote location searches ───────────────────────────────────────────────
    if locs_remote:
        lines.append(
            "\nRemote location searches — for each location below, search with remote=True ONLY "
            "(always remote regardless of location type chips):"
        )
        for loc in locs_remote:
            lines.append(f"  - {loc}")
    elif "remote" in loc_types and not locs_remote:
        lines.append("\nRemote search: search remote jobs with no specific location restriction.")

    # ── Other filters ──────────────────────────────────────────────────────────
    if emp_types:
        lines.append(f"\nEmployment types: {', '.join(emp_map.get(t, t) for t in emp_types)}")
    if exp_levels:
        lines.append(f"Experience levels: {', '.join(level_map.get(l, l) for l in exp_levels)}")
    if min_salary:
        lines.append(f"Minimum salary: ${int(min_salary):,}+")

    lines.append("=== END PREFERENCES ===")
    return "\n".join(lines)


def extract_json(text: str) -> dict:
    for pattern in [r'```json\s*(\{.*?\})\s*```', r'```\s*(\{.*?\})\s*```', r'(\{.*\})']:
        m = re.search(pattern, text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1))
            except Exception:
                continue
    return {}


def polish_section(key: str, answers: dict, loop_items: list = None) -> dict:
    """Call Ollama to convert raw answers into polished resume data. Returns structured dict."""

    if key == 'summary':
        prompt = f"""Convert these raw answers into exactly 3 professional resume summary paragraphs.
Keep each paragraph to 2-3 sentences. Use professional, achievement-focused language. Do not add bullet points.

Background: {answers.get('background', '')}
Current work/study: {answers.get('current', '')}
Passion/goals: {answers.get('passion', '')}

Output ONLY valid JSON (no extra text):
{{"summary": ["paragraph one", "paragraph two", "paragraph three"]}}"""

    elif key == 'expertise':
        prompt = f"""Convert this list into 10-12 clean, professional resume expertise labels.
Each label should be 2-5 words, Title Case, professional and specific.

Input: {answers.get('raw', '')}

Output ONLY valid JSON (no extra text):
{{"expertise": ["Label One", "Label Two", ...]}}"""

    elif key == 'experience':
        prompt = f"""Convert this job description into 3-5 strong resume bullet points.
Start each bullet with a powerful action verb. Be specific and achievement-focused. Do not include "▪" or bullet characters.

Company: {answers.get('company', '')}
Title: {answers.get('title', '')}
Responsibilities: {answers.get('responsibilities', '')}

Output ONLY valid JSON (no extra text):
{{"bullets": ["Bullet one text", "Bullet two text", ...]}}"""

    elif key == 'certifications':
        prompt = f"""Convert this certifications list into clean, standardized entries.
Format each as "Certification Name – Issuer, Year" or "Certification Name – Issuer, Year (in-progress)".

Input: {answers.get('raw', '')}

Output ONLY valid JSON (no extra text):
{{"certifications": ["entry one", "entry two", ...]}}"""

    elif key == 'skills':
        prompt = f"""Organize these technical skills into clear, professional categories for a resume.
Each category should have a clear name and a comma-separated list of items.

Input: {answers.get('raw', '')}

Output ONLY valid JSON (no extra text):
{{"skills": [{{"category": "Category Name", "items": "Item1, Item2, Item3"}}, ...]}}"""

    else:
        return {}

    raw = call_ollama([{'role': 'user', 'content': prompt}])
    return extract_json(raw)


# ── Section → resume_data mapping ────────────────────────────────────────────

def apply_section(key: str, answers: dict, loop_items: list, polished: dict) -> None:
    """Write completed section data into state['resume_data']."""
    rd = state['resume_data']

    if key == 'meta':
        rd['meta'].update({
            'name':           answers.get('name', ''),
            'location':       answers.get('location', ''),
            'phone':          answers.get('phone', ''),
            'email':          answers.get('email', ''),
            'linkedin_label': answers.get('linkedin_label', 'LinkedIn Profile'),
            'linkedin_url':   answers.get('linkedin_url', ''),
        })

    elif key == 'title':
        rd['title'] = answers.get('raw', '')

    elif key == 'summary':
        rd['summary'] = polished.get('summary', [answers.get('background', '')])

    elif key == 'expertise':
        rd['expertise'] = polished.get('expertise', [a.strip() for a in answers.get('raw', '').split(',')])

    elif key == 'experience':
        for item in loop_items:
            rd['experience'].append({
                'company':  item['answers'].get('company', ''),
                'location': item['answers'].get('location', ''),
                'title':    item['answers'].get('title', ''),
                'dates':    item['answers'].get('dates', ''),
                'bullets':  item['polished'].get('bullets', []),
            })

    elif key == 'education':
        for item in loop_items:
            rd['education'].append({
                'degree':      item['answers'].get('degree', ''),
                'institution': item['answers'].get('institution', ''),
                'location':    item['answers'].get('location', ''),
                'year':        item['answers'].get('year', ''),
            })

    elif key == 'certifications':
        rd['certifications'] = polished.get('certifications',
            [c.strip() for c in answers.get('raw', '').split('\n') if c.strip()])

    elif key == 'skills':
        rd['skills'] = polished.get('skills', [{'category': 'Skills', 'items': answers.get('raw', '')}])

    elif key == 'languages':
        raw = answers.get('raw', '')
        # Format: "English – Native, Spanish – Conversational" → "English (Native) | Spanish (Conversational)"
        parts = [p.strip() for p in re.split(r',|\n', raw) if p.strip()]
        formatted = ' | '.join(parts)
        rd['languages'] = formatted


# ── Section HTML rendering ────────────────────────────────────────────────────

def render_section_html(key: str) -> str:
    """Render just the #section-[key] div using the current resume_data."""
    env = Environment(loader=FileSystemLoader(str(TMPL_DIR)))
    full = env.get_template('resume_partial.html').render(**state['resume_data'])
    # Extract just the target section div
    m = re.search(rf'<div id="section-{key}">(.*?)</div>\s*(?=\n*<div id="section-|$)',
                  full, re.DOTALL)
    if m:
        return f'<div id="section-{key}">{m.group(1)}</div>'
    return ''


# ── Loaded-mode coaching ──────────────────────────────────────────────────────

def _resume_as_text(rd: dict) -> str:
    """Render the full resume as plain text for Ollama context."""
    lines = []

    m = rd.get('meta', {})
    lines.append(f"NAME: {m.get('name', '')}")
    lines.append(f"CONTACT: {m.get('location', '')} | {m.get('phone', '')} | {m.get('email', '')} | {m.get('linkedin_url', '')}")
    lines.append(f"TITLE: {rd.get('title', '')}")

    lines.append("\nSUMMARY:")
    for i, para in enumerate(rd.get('summary', []), 1):
        lines.append(f"  Paragraph {i}: {para.strip()}")

    lines.append("\nEXPERTISE:")
    for item in rd.get('expertise', []):
        lines.append(f"  - {item}")

    lines.append("\nEXPERIENCE:")
    for job in rd.get('experience', []):
        lines.append(f"  {job.get('company', '')} | {job.get('location', '')} | {job.get('title', '')} | {job.get('dates', '')}")
        for b in job.get('bullets', []):
            lines.append(f"    • {b.strip()}")

    lines.append("\nEDUCATION:")
    for edu in rd.get('education', []):
        lines.append(f"  {edu.get('degree', '')} — {edu.get('institution', '')} ({edu.get('year', '')})")

    lines.append("\nCERTIFICATIONS:")
    for cert in rd.get('certifications', []):
        lines.append(f"  - {cert}")

    lines.append("\nSKILLS:")
    for skill in rd.get('skills', []):
        lines.append(f"  {skill.get('category', '')}: {str(skill.get('items', '')).strip()}")

    lines.append(f"\nLANGUAGES: {rd.get('languages', '')}")

    return '\n'.join(lines)


def chat_coach_mode(user_msg: str) -> dict:
    """Free-form resume coaching when a resume is already loaded."""
    rd = state['resume_data']
    name  = rd.get('meta', {}).get('name', 'the candidate')
    title = rd.get('title', '')
    resume_text = _resume_as_text(rd)

    memory_block   = format_memory_block(load_memory())
    memory_section = f"\n{memory_block}\n" if memory_block else ""

    system = f"""You are an expert resume strategist and career coach for tech and cloud roles. You are working exclusively with {name}, targeting: {title}.

You have studied their full resume carefully. Think critically before responding — your job is not just to do what is asked, but to give the best possible advice.

How to respond:
1. ANALYZE first: Before making any change, assess whether the request makes sense given the full resume. Identify any issues in the current text (outdated info, wrong tense, weak framing, inconsistencies).
2. ADVISE: Share your honest assessment in 1-2 sentences. Flag anything that needs correcting even if they didn't ask.
3. SUGGEST: Provide your recommended version, clean and paste-ready.

Example — if someone asks to "rephrase" a sentence that still says "currently completing" but they already graduated, don't just rephrase it. Point out the outdated framing and fix that too.

Standards to enforce:
- Past tense for completed roles and programs; present tense only for current active work
- Action verbs, specific achievements, no vague filler language
- Consistency in tone and detail level across all sections
- Never invent facts not in the resume

Formatting rules (strictly follow):
- Plain text only — no markdown, no bold (**), no bullet symbols (-, *, •), no headers (#), no backticks
- Use numbered steps (1. 2. 3.) only when listing a sequence; otherwise write in paragraphs
- Separate your analysis, advice, and suggestion with a blank line between each — do not label them with headers
{memory_section}
Full resume:
=== RESUME ===
{resume_text}
=== END RESUME ==="""

    # Append user message to history and log to disk
    state['chat_history'].append({'role': 'user', 'content': user_msg})
    log_turn('user', user_msg)

    messages = [{'role': 'system', 'content': system}] + state['chat_history']
    reply = call_ollama(messages, think=True)

    # Store assistant reply in history and log to disk
    state['chat_history'].append({'role': 'assistant', 'content': reply})
    log_turn('assistant', reply)

    return {"reply": reply, "update": None}


# ── Q&A state machine helpers ─────────────────────────────────────────────────

def current_section() -> dict:
    return SECTIONS[state['section_idx']]


def current_question() -> tuple:
    sec = current_section()
    return sec['questions'][state['question_idx']]


def transition_message(next_sec: dict) -> str:
    return f"Great! Now let's move to **{next_sec['label']}**.\n\n{next_sec['intro']}\n\n{next_sec['questions'][0][1]}"


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/agent")
def agent():
    return render_template("agent.html")


@app.route("/jobs")
def jobs():
    return render_template("jobs.html")


@app.route("/load")
def load():
    global resume_state
    if not BASE_YAML.exists():
        return jsonify({"error": "resume-base.yaml not found"}), 404
    resume_state = _load_yaml(BASE_YAML)
    state['resume_data'] = resume_state
    state['loaded'] = True
    state['chat_history'] = []
    state['session_file'] = _new_session_file()
    env = Environment(loader=FileSystemLoader(str(TMPL_DIR)))
    html = env.get_template('resume_partial.html').render(**resume_state)
    return jsonify({"html": html, "data": resume_state})


@app.route("/api/state")
def api_state():
    """Return current session state so the page can restore without re-loading."""
    if not state.get('loaded'):
        return jsonify({"loaded": False})
    env = Environment(loader=FileSystemLoader(str(TMPL_DIR)))
    html = env.get_template('resume_partial.html').render(**state['resume_data'])
    return jsonify({"loaded": True, "html": html, "data": state['resume_data']})


@app.route("/api/start")
def api_start():
    """Reset state and return the first question."""
    global state
    state = fresh_state()
    sec = current_section()
    msg = f"{sec['intro']}\n\n{sec['questions'][0][1]}"
    return jsonify({"reply": msg})


@app.route("/api/chat", methods=["POST"])
def api_chat():
    body     = request.get_json()
    user_msg = body.get("message", "").strip()
    if not user_msg:
        return jsonify({"reply": "I didn't catch that — could you try again?", "update": None})

    # Loaded-mode: resume already exists — use free-form coaching, not the Q&A flow
    if state.get('loaded'):
        result = chat_coach_mode(user_msg)
        return jsonify(result)

    sec = current_section()

    # ── Loop confirm branch ───────────────────────────────────────
    if state['awaiting_loop_confirm']:
        state['awaiting_loop_confirm'] = False
        if user_msg.lower().startswith('y'):
            # Another item — reset question_idx, clear answers
            state['question_idx'] = 0
            state['answers'] = {}
            _, q = current_question()
            return jsonify({"reply": f"Sure! {q}", "update": None})
        else:
            # Done with loop — finalise section
            return _finalise_section()

    # ── Store answer for current question ─────────────────────────
    field, _ = current_question()
    state['answers'][field] = user_msg
    state['question_idx'] += 1

    # ── More questions in this section? ──────────────────────────
    if state['question_idx'] < len(sec['questions']):
        _, next_q = current_question()
        return jsonify({"reply": next_q, "update": None})

    # ── All questions answered ────────────────────────────────────
    if sec.get('loop'):
        # Polish this loop item (experience/education)
        polished = polish_section(sec['key'], state['answers']) if sec['polish'] else {}
        state['loop_items'].append({'answers': dict(state['answers']), 'polished': polished})
        state['answers'] = {}
        state['question_idx'] = 0
        state['awaiting_loop_confirm'] = True
        return jsonify({"reply": sec['loop_question'], "update": None})

    return _finalise_section()


def _finalise_section():
    sec = current_section()

    # Polish if needed
    polished = polish_section(sec['key'], state['answers'], state['loop_items']) if sec['polish'] else {}

    # Write into resume_data
    apply_section(sec['key'], state['answers'], state['loop_items'], polished)

    # Reset for next section
    state['answers'] = {}
    state['loop_items'] = []
    state['question_idx'] = 0

    # Render updated section HTML
    section_html = render_section_html(sec['key'])

    # Advance to next section
    state['section_idx'] += 1

    if state['section_idx'] >= len(SECTIONS):
        return jsonify({
            "reply": "Your resume is complete! Review it on the right, edit anything inline, then hit Save or Export PDF.",
            "update":     {"section": sec['key'], "html": section_html},
            "state_data": state['resume_data'],
            "done": True,
        })

    next_sec = SECTIONS[state['section_idx']]
    reply = f"Done! ✓\n\n{transition_message(next_sec)}"
    return jsonify({
        "reply":      reply,
        "update":     {"section": sec['key'], "html": section_html},
        "state_data": state['resume_data'],
    })


@app.route("/api/save", methods=["POST"])
def api_save():
    """Write the client's resumeState back to resume-base.yaml."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data received"}), 400
    try:
        with open(BASE_YAML, "w") as f:
            yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
        state['resume_data'] = data
        return jsonify({"ok": True, "message": "Resume saved."})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/export")
def export():
    """Render current resume_data to PDF and return as download."""
    import copy, tempfile
    from flask import send_file

    data = state.get('resume_data') or {}
    if not data:
        return "No resume data — complete the Q&A or load your resume first.", 400

    # Write a temp YAML, call render.py logic directly
    try:
        from render import render_html, export_pdf

        html  = render_html(data)
        fname = f"resume-{data.get('meta', {}).get('name', 'export').replace(' ', '_')}.pdf"
        tmp   = Path(tempfile.mkdtemp()) / fname
        export_pdf(html, tmp)
        return send_file(str(tmp), as_attachment=True, download_name=fname,
                         mimetype="application/pdf")
    except Exception as e:
        return f"Export failed: {e}", 500


# ── F003 — Agent tool definitions ────────────────────────────────────────────

MAX_TOOL_ITERATIONS = 10

AGENT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_jobs",
            "description": "Search major job boards: LinkedIn, Indeed, Glassdoor, Google Jobs, ZipRecruiter",
            "parameters": {
                "type": "object",
                "properties": {
                    "query":          {"type": "string", "description": "Job title or keywords"},
                    "location":       {"type": "string", "description": "City, country, or 'remote'"},
                    "job_type":       {"type": "string", "enum": ["fulltime", "parttime", "contract", "internship"]},
                    "remote":         {"type": "boolean"},
                    "results_wanted": {"type": "integer", "default": 15},
                },
                "required": ["query", "location"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_remote_jobs",
            "description": "Search Himalayas for remote-only jobs worldwide",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_eu_jobs",
            "description": "Search Arbeitnow for EU-based and remote jobs",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
    },
]


def get_active_tools(active_sources: list) -> list:
    """Return only the tool definitions relevant to the user's enabled sources."""
    jobspy_names = {"linkedin", "indeed", "glassdoor", "google", "ziprecruiter"}
    include_jobspy    = bool(set(active_sources) & jobspy_names)
    include_himalayas = "himalayas" in active_sources
    include_arbeitnow = "arbeitnow" in active_sources
    return [
        t for t in AGENT_TOOLS if
        (t["function"]["name"] == "search_jobs"        and include_jobspy) or
        (t["function"]["name"] == "search_remote_jobs" and include_himalayas) or
        (t["function"]["name"] == "search_eu_jobs"     and include_arbeitnow)
    ]


def batch_score_jobs(criteria: dict, jobs: list) -> dict:
    """Score all scraped jobs in a single LLM call. Returns {url: score}."""
    prompt = (
        f"Job search criteria: {json.dumps(criteria)}\n\n"
        "Score each job 1–10 for relevance to the criteria above.\n"
        "Return ONLY valid JSON, no other text:\n"
        '[{"url": "<url>", "score": <int>}, ...]\n\n'
        "Jobs:\n"
    ) + "\n".join(
        f"{i+1}. Title: {j.get('title','')} | Company: {j.get('company','')} | "
        f"Location: {j.get('location','')} | URL: {j.get('url','')}"
        for i, j in enumerate(jobs)
    )
    raw = call_ollama([{"role": "user", "content": prompt}])
    try:
        scored = json.loads(re.search(r"\[.*\]", raw, re.DOTALL).group())
        return {item["url"]: int(item["score"]) for item in scored}
    except Exception:
        return {}


# ── F003 — Job board routes ───────────────────────────────────────────────────

@app.route("/api/preferences")
def api_prefs_get():
    try:
        data = json.loads(PREFS_FILE.read_text()) if PREFS_FILE.exists() else {}
    except Exception:
        data = {}
    return jsonify(data)


@app.route("/api/preferences", methods=["POST"])
def api_prefs_save():
    incoming = request.get_json() or {}
    try:
        existing = {}
        if PREFS_FILE.exists():
            try:
                existing = json.loads(PREFS_FILE.read_text())
            except Exception:
                pass
        existing.update(incoming)
        PREFS_FILE.write_text(json.dumps(existing, indent=2, ensure_ascii=False))
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/preferences/filters", methods=["POST"])
def api_prefs_filters_save():
    incoming = request.get_json() or {}
    try:
        existing = {}
        if PREFS_FILE.exists():
            try:
                existing = json.loads(PREFS_FILE.read_text())
            except Exception:
                pass
        for key in ("experience_levels", "min_salary"):
            if key in incoming:
                existing[key] = incoming[key]
        PREFS_FILE.write_text(json.dumps(existing, indent=2, ensure_ascii=False))
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/jobs")
def api_jobs():
    filters = {
        "source":    request.args.get("source", "all"),
        "status":    request.args.get("status", "all"),
        "min_score": request.args.get("min_score", ""),
        "job_type":  request.args.get("job_type", "all"),
        "remote":    request.args.get("remote", ""),
        "days_ago":  request.args.get("days_ago", ""),
        "page":      request.args.get("page", 1),
    }
    jobs, total = get_jobs(filters)
    return jsonify({"jobs": jobs, "total": total, "page_size": 25})


@app.route("/api/job/<int:job_id>/save", methods=["POST"])
def api_job_save(job_id):
    update_status(job_id, "saved")
    return jsonify({"ok": True})


@app.route("/api/job/<int:job_id>/dismiss", methods=["POST"])
def api_job_dismiss(job_id):
    update_status(job_id, "dismissed")
    return jsonify({"ok": True})


@app.route("/api/export/jobs")
def api_export_jobs():
    csv_content = export_csv()
    filename = f"saved-jobs-{datetime.now().strftime('%Y-%m-%d')}.csv"
    return Response(
        csv_content,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# ── F003 — Agent routes ──────────────────────────────────────────────────────

@app.route("/api/agent/reset", methods=["POST"])
def api_agent_reset():
    global agent_state
    agent_state = {"messages": [], "search_criteria": {}, "active_sources": [], "search_done": False}
    return jsonify({"ok": True})


@app.route("/api/agent/stop", methods=["POST"])
def api_agent_stop():
    _stop_event.set()
    return jsonify({"ok": True})


@app.route("/api/agent/chat", methods=["POST"])
def api_agent_chat():
    global agent_state
    body    = request.get_json()
    msg     = body.get("message", "").strip()
    sources = body.get("sources", [])
    if not msg:
        return jsonify({"reply": "I didn't catch that — try again.", "done": False})

    _stop_event.clear()
    agent_state["active_sources"] = sources
    active_tools = get_active_tools(sources)

    print(f"\n[agent] ── New request ──────────────────────────")
    print(f"[agent] Message : {msg[:120]}")
    print(f"[agent] Sources : {sources}")
    print(f"[agent] Tools   : {[t['function']['name'] for t in active_tools]}")

    # Inject system prompt + preferences on the very first user message
    if not agent_state["messages"]:
        system_prompt = """You are a job search assistant. Follow these rules exactly when searching for jobs:

SEARCH RULES:
1. On-site location searches: For each location listed under "On-site location searches" in the preferences, call search_jobs ONCE with:
   - query: all job titles combined (e.g. "Software Engineer Cloud Engineer")
   - location: that specific location
   - remote: False
   - The selected job types (On-site, Hybrid, Remote) are informational — always use remote=False for on-site location searches

2. Remote location searches: For each location listed under "Remote location searches", call search_jobs ONCE with:
   - query: all job titles combined
   - location: that region
   - remote: True (ALWAYS, regardless of anything else)

3. ONE call per location — never multiply by title. Combine all titles into one query string.
4. If a section says "skip", do not make any call for it.
5. After all searches complete, summarize what was found in 2-3 sentences and stop."""
        agent_state["messages"].append({"role": "system", "content": system_prompt})
        print(f"[agent] System prompt injected")

        pref_block = _format_preferences()
        if pref_block:
            print(f"[agent] Preferences injected into context")
            msg = f"{pref_block}\n\n{msg}"
        else:
            print(f"[agent] No saved preferences found")

    agent_state["messages"].append({"role": "user", "content": msg})

    all_jobs      = []
    source_errors = []
    iterations    = 0

    while iterations < MAX_TOOL_ITERATIONS:
        if _stop_event.is_set():
            return jsonify({"reply": "Search stopped.", "done": False})
        iterations += 1
        print(f"[agent] Iteration {iterations} — calling Ollama ({AGENT_MODEL})...")
        try:
            content, tool_calls = call_ollama_with_tools(agent_state["messages"], active_tools)
        except Exception as e:
            print(f"[agent] ERROR — Ollama failed on iteration {iterations}: {e}")
            return jsonify({"error": "Agent timed out — try again.", "done": False})

        if not tool_calls:
            print(f"[agent] No tool calls — agent is done, composing reply")
            agent_state["messages"].append({"role": "assistant", "content": content})
            break

        print(f"[agent] Tool calls requested: {[tc['function']['name'] for tc in tool_calls]}")
        agent_state["messages"].append({"role": "assistant", "content": content, "tool_calls": tool_calls})

        for tc in tool_calls:
            fn   = tc["function"]["name"]
            args = tc["function"].get("arguments") or {}
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except Exception:
                    args = {}

            if fn == "search_jobs":
                agent_state["search_criteria"] = args
                jobspy_sources = [s for s in sources if s in {"linkedin", "indeed", "glassdoor", "google", "ziprecruiter"}]
                print(f"[agent] Scraping job boards: {jobspy_sources}")
                print(f"[agent]   query={args.get('query')}  location={args.get('location')}  remote={args.get('remote')}  job_type={args.get('job_type')}")
                result, errs = run_jobspy(
                    query=args.get("query", ""),
                    location=args.get("location", "remote"),
                    job_type=args.get("job_type", "fulltime"),
                    remote=args.get("remote", False),
                    sources=jobspy_sources,
                    results_per_source=args.get("results_wanted", 15),
                )
                print(f"[agent] Job boards returned {len(result)} jobs" + (f" | errors: {errs}" if errs else ""))
                source_errors.extend(errs)
            elif fn == "search_remote_jobs":
                if not agent_state["search_criteria"]:
                    agent_state["search_criteria"] = {"query": args.get("query", "")}
                print(f"[agent] Scraping Himalayas: query={args.get('query')}")
                result, errs = run_himalayas(args.get("query", ""))
                print(f"[agent] Himalayas returned {len(result)} jobs" + (f" | errors: {errs}" if errs else ""))
                source_errors.extend(errs)
            elif fn == "search_eu_jobs":
                if not agent_state["search_criteria"]:
                    agent_state["search_criteria"] = {"query": args.get("query", "")}
                print(f"[agent] Scraping Arbeitnow: query={args.get('query')}")
                result, errs = run_arbeitnow(args.get("query", ""))
                print(f"[agent] Arbeitnow returned {len(result)} jobs" + (f" | errors: {errs}" if errs else ""))
                source_errors.extend(errs)
            else:
                result = []

            all_jobs.extend(result)
            agent_state["messages"].append({
                "role":    "tool",
                "name":    fn,
                "content": json.dumps({"count": len(result), "sample": result[:2]}),
            })

    job_count = 0
    if all_jobs and not agent_state["search_done"]:
        print(f"[agent] Scoring {len(all_jobs)} jobs with LLM...")
        scores = batch_score_jobs(agent_state["search_criteria"], all_jobs)
        for job in all_jobs:
            job["match_score"] = scores.get(job.get("url", ""), 0)
        print(f"[agent] Scoring done — saving to database...")
        job_count = insert_jobs(all_jobs)
        if scores:
            update_scores(scores)
        agent_state["search_done"] = True
        print(f"[agent] Done — {job_count} jobs saved to database")
    elif not all_jobs and agent_state["search_done"] is False:
        print(f"[agent] No jobs collected — skipping score/save")

    print(f"[agent] ── Request complete ─────────────────────\n")
    final_reply = agent_state["messages"][-1]["content"] if agent_state["messages"] else ""
    return jsonify({"reply": final_reply, "done": agent_state["search_done"],
                    "job_count": job_count, "source_errors": source_errors})


# ── F004 — Memory routes ─────────────────────────────────────────────────────

@app.route("/api/memory/end-session", methods=["POST"])
def api_memory_end_session():
    session_file = state.get("session_file")
    if not session_file or not Path(session_file).exists():
        return jsonify({"error": "No session log found"}), 400

    # Read session turns
    turns = []
    with open(session_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    turns.append(json.loads(line))
                except Exception:
                    pass

    if not turns:
        return jsonify({"error": "Session log is empty"}), 400

    session_text = "\n".join(f"[{t['role'].upper()}] {t['content']}" for t in turns)

    # Load current memory for context
    current = load_memory()
    existing_facts   = current["facts"]
    existing_pending = current["pending"]

    prompt = f"""Here is today's coaching session:

{session_text}

Existing facts already known (do not repeat these):
{json.dumps(existing_facts)}

Existing pending tasks (do not repeat these):
{json.dumps(existing_pending)}

Extract and return JSON with:
1. "new_facts": any NEW facts about the user, resume, or goals discovered today (not already in existing facts)
2. "completed": tasks completed in this session (be specific)
3. "pending": NEW tasks mentioned or identified but not yet done (not already in existing pending)
4. "remove_pending": any existing pending tasks that are now done (exact match strings from the list above)

Only include items that are genuinely new or resolved. Return empty lists if nothing qualifies.
Return ONLY valid JSON, no other text:
{{"new_facts": [], "completed": [], "pending": [], "remove_pending": []}}"""

    raw = call_ollama([{"role": "user", "content": prompt}], think=True)
    extracted = extract_json(raw)

    # Merge into memory
    facts_list = list(existing_facts)
    for f in extracted.get("new_facts", []):
        if f and f not in facts_list:
            facts_list.append(f)

    completed_list = list(current["completed"])
    for c in extracted.get("completed", []):
        if c:
            completed_list.append(c)

    pending_list = list(existing_pending)
    remove_set = set(extracted.get("remove_pending", []))
    pending_list = [p for p in pending_list if p not in remove_set]
    for p in extracted.get("pending", []):
        if p and p not in pending_list:
            pending_list.append(p)

    save_memory(facts_list, {"completed": completed_list, "pending": pending_list})

    updated = {"facts": facts_list, "completed": completed_list, "pending": pending_list}
    return jsonify({"ok": True, "memory": updated})


@app.route("/api/memory")
def api_memory_get():
    return jsonify(load_memory())


@app.route("/api/memory/fact", methods=["POST"])
def api_memory_add_fact():
    fact = (request.get_json() or {}).get("fact", "").strip()
    if not fact:
        return jsonify({"error": "fact is required"}), 400
    mem = load_memory()
    if fact not in mem["facts"]:
        mem["facts"].append(fact)
        save_memory(mem["facts"], {"completed": mem["completed"], "pending": mem["pending"]})
    return jsonify({"ok": True, "facts": mem["facts"]})


@app.route("/api/memory/fact/<int:idx>", methods=["DELETE"])
def api_memory_delete_fact(idx):
    mem = load_memory()
    if idx < 0 or idx >= len(mem["facts"]):
        return jsonify({"error": "index out of range"}), 400
    mem["facts"].pop(idx)
    save_memory(mem["facts"], {"completed": mem["completed"], "pending": mem["pending"]})
    return jsonify({"ok": True, "facts": mem["facts"]})


@app.route("/api/memory/pending/<int:idx>", methods=["DELETE"])
def api_memory_delete_pending(idx):
    mem = load_memory()
    if idx < 0 or idx >= len(mem["pending"]):
        return jsonify({"error": "index out of range"}), 400
    mem["pending"].pop(idx)
    save_memory(mem["facts"], {"completed": mem["completed"], "pending": mem["pending"]})
    return jsonify({"ok": True, "pending": mem["pending"]})


# ── Utilities ─────────────────────────────────────────────────────────────────

def _load_yaml(path: Path) -> dict:
    with open(path) as f:
        return yaml.safe_load(f) or {}


if __name__ == "__main__":
    print("Resume Builder running at http://localhost:5000")
    app.run(debug=True, port=5000)
