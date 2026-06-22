<div align="center">
  <img src="assets/icon.jpeg" alt="Skillora" width="100" />

  # Skillora

  **A private, local-first AI platform for job discovery, resume tailoring, and candidate coaching.**

  ![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat&logo=python&logoColor=white)
  ![Flask](https://img.shields.io/badge/Flask-3.0-black?style=flat&logo=flask&logoColor=white)
  ![Ollama](https://img.shields.io/badge/Ollama-Local%20LLM-white?style=flat)
  ![License](https://img.shields.io/badge/License-MIT-green?style=flat)
</div>

---

Skillora automates the most time-consuming parts of a job search — finding relevant listings across seven sources, scoring them against your profile with a local LLM, tailoring your resume per role, and maintaining coaching context across sessions. Everything runs on your machine. No SaaS subscriptions, no third-party data sharing, no API costs.

---

## Features

### AI Job Search Agent
Describe what you're looking for in plain English. The agent searches **LinkedIn, Indeed, Glassdoor, Google Jobs, ZipRecruiter, Himalayas, and Arbeitnow** simultaneously, then scores every result for relevance against your candidate profile using a local LLM. Results land on a filterable review board where you can save, dismiss, apply, or export to CSV.

### Resume Engine
A YAML-driven resume system built around a single master file with per-job override support. Write your resume once, generate an unlimited number of tailored variants — each one exported to a pixel-accurate PDF via Playwright and a custom HTML/CSS template. No formatting work between applications.

### AI Resume Coach
A Flask web app with a built-in Ollama coaching chatbot that walks through your resume section by section, offering targeted feedback and suggestions. Every field is inline-editable directly in the browser. One click saves back to YAML; another exports to PDF.

### Persistent LLM Memory
The coaching session is logged and summarized automatically at the end of each conversation. Extracted facts and pending tasks are injected back into the system prompt on the next session — so the coach always knows your background, what was already improved, and what's still outstanding, without you having to repeat yourself.

### Job Preferences & Saved Filters
A persistent sidebar lets you configure job titles, location types, employment types, experience levels, salary minimum, and source toggles once. Preferences are stored server-side and automatically applied to every new search — no re-entering criteria each session.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.12, Flask |
| LLM | Ollama — runs fully local (`qwen3:32b`) |
| Job scraping | python-jobspy · Himalayas API · Arbeitnow API |
| Resume rendering | Jinja2 + Playwright (headless Chromium → PDF) |
| Storage | SQLite (jobs) · JSON (memory, preferences) |
| Frontend | Vanilla JS, HTML/CSS |

---

## Prerequisites

- Python 3.10+
- [Ollama](https://ollama.com) installed and running
- ~20 GB disk space for the LLM model

---

## Installation

```bash
# Clone the repository
git clone https://github.com/Allexzaa/Skillora.git
cd Skillora

# Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate       # Mac / Linux
# .venv\Scripts\activate        # Windows

# Install dependencies
pip install -r webapp/requirements.txt

# Install Playwright's headless browser (required for PDF export)
playwright install chromium

# Pull the Ollama model (one-time download)
ollama pull qwen3:32b
```

---

## Running Skillora

```bash
source .venv/bin/activate
python webapp/app.py
```

Open **http://localhost:5000** in your browser.

| Route | What it does |
|---|---|
| `/` | Resume Coach — AI Q&A, inline editing, PDF export |
| `/agent` | Job Search Agent — describe a role and trigger a multi-source search |
| `/jobs` | Job Results Board — filter, review, save, apply, export CSV |

---

## Resume Setup

Skillora's resume engine uses a plain YAML file as your master resume:

1. Create `resume/resume-base.yaml` with your personal details (see the template structure in `resume/template.html`)
2. Run the coach at `/` to build it interactively, or edit the YAML directly
3. Create per-job overrides in `resume/overrides/resume-[slug].yaml` — only include the fields you want to change
4. Export to PDF with one click from the web app, or via CLI:

```bash
cd resume
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium

python render.py                           # Export base resume to PDF
python render.py --job [slug]              # Export with job-specific overrides
python render.py --preview                 # Preview in browser without generating PDF
```

PDFs are written to `resume/output/`.

---

## Project Structure

```
Skillora/
├── webapp/
│   ├── app.py              # Flask application — all routes and LLM logic
│   ├── db.py               # SQLite job storage layer
│   ├── scrapers.py         # Job board scraper functions
│   ├── requirements.txt    # Dependencies
│   └── templates/
│       ├── index.html      # Resume Coach
│       ├── agent.html      # Job Search Agent
│       ├── jobs.html       # Job Results Board
│       └── resume_partial.html
└── resume/
    ├── render.py           # CLI PDF renderer
    ├── template.html       # Jinja2 + CSS resume template
    └── requirements.txt    # Resume module dependencies
```

---

## Privacy

All data stays on your machine. Resume content, session history, job preferences, and LLM conversations never leave localhost. Ollama runs the model locally with no external calls. Job scraping queries the listed job boards directly — there is no intermediary server.
