<img src="assets/icon.jpeg" alt="Skillora" width="72" />

# Skillora

**Private AI Job Search OS** — a fully local platform for job discovery, resume tailoring, and candidate coaching. No SaaS. No third-party data sharing. Everything runs on your machine.

---

## Overview

Skillora automates the most time-consuming parts of a job search — finding relevant listings, scoring them against your profile, tailoring your resume, and maintaining coaching context across sessions — using a local LLM (Ollama) and Playwright-powered scrapers. The entire pipeline runs offline.

The system is built around three interfaces:

| Page | Path | Purpose |
|---|---|---|
| Resume Coach | `/` | AI-guided resume builder with inline editing and PDF export |
| Job Search Agent | `/agent` | Conversational agent that triggers multi-source scraping |
| Job Results Board | `/jobs` | Filterable job board with save, dismiss, apply, and CSV export |

---

## Features

### Resume Engine (F001 + F002)
- YAML-driven master resume with per-job override system — one base file, unlimited tailored variants
- Jinja2 HTML template renders to pixel-accurate PDF via Playwright
- Flask web app with AI-guided Q&A (Ollama) that builds a resume section by section
- Inline `contenteditable` editing for every field; one-click save back to YAML and one-click PDF export
- Persistent LLM memory injects past session facts and pending tasks into the next coaching session

### Job Scraper Agent (F003)
- Conversational agent UI — describe a role in plain English, the agent calls the scrapers
- Pulls from **7 sources**: LinkedIn, Indeed, Glassdoor, Google Jobs, ZipRecruiter, Himalayas, Arbeitnow
- Local LLM relevance scoring against your candidate profile — each result gets a score and reasoning
- Configurable rate limits and per-source result caps to avoid blocks
- Results stored in SQLite; board supports save / dismiss / apply status tracking

### Job Preferences & Filters (F005)
- Persistent sidebar on both the Agent and Results pages
- Source toggle cards, job title chips, location type (remote / on-site / hybrid), locations, employment type
- Filters: date posted, experience level, salary minimum
- Preferences stored server-side and automatically injected into the agent's system prompt on every search

### Persistent LLM Memory (F004)
- Every coaching session is logged to disk as a JSONL file
- After session end, the LLM extracts structured facts and a pending task list
- Extracted memory is injected into the system prompt on the next session — the coach remembers without re-prompting
- Memory drawer in the UI shows current facts and work log; individual entries can be deleted

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.12, Flask |
| LLM | Ollama (`qwen3:32b`) — runs fully local |
| Scraping | python-jobspy (LinkedIn / Indeed / Glassdoor / Google / ZipRecruiter), Himalayas API, Arbeitnow API |
| Resume rendering | Jinja2 + Playwright (headless Chromium → PDF) |
| Storage | SQLite (jobs), JSON files (memory, preferences) |
| Frontend | Vanilla JS, HTML/CSS (no framework) |

---

## Setup

**Prerequisites:** Python 3.10+, [Ollama](https://ollama.com) installed and running

```bash
# 1. Clone the repo
git clone https://github.com/Allexzaa/Skillora.git
cd Skillora

# 2. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate        # Mac / Linux
# .venv\Scripts\activate         # Windows

# 3. Install dependencies
pip install -r webapp/requirements.txt

# 4. Install Playwright's Chromium (required for PDF export)
playwright install chromium

# 5. Pull the Ollama model (one-time, ~20 GB)
ollama pull qwen3:32b
```

---

## Running the App

```bash
# From project root, with .venv active
source .venv/bin/activate
python webapp/app.py
```

Open [http://localhost:5000](http://localhost:5000) in your browser.

| Route | Description |
|---|---|
| `http://localhost:5000/` | Resume Coach — AI Q&A, inline editing, PDF export |
| `http://localhost:5000/agent` | Job Search Agent — describe a role, trigger scraping |
| `http://localhost:5000/jobs` | Job Results Board — filter, save, apply, export CSV |

---

## Resume CLI (headless)

For PDF generation without the web app:

```bash
cd resume
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium

# Preview in browser (instant)
python render.py --preview
python render.py --job sample --preview

# Export to PDF
python render.py
python render.py --job sample
python render.py --job sample --out "FirstName_LastName_Role.pdf"
```

- Copy `resume/resume-base.example.yaml` → `resume/resume-base.yaml` and fill in your details
- Edit `resume/template.html` for design
- Create `resume/overrides/resume-[slug].yaml` for per-job overrides
- PDFs are written to `resume/output/`

---

## Project Structure

```
Skillora/
├── webapp/
│   ├── app.py              # Flask app — all routes and LLM logic
│   ├── db.py               # SQLite job storage
│   ├── scrapers.py         # JobSpy, Himalayas, Arbeitnow scraper functions
│   ├── requirements.txt    # Webapp dependencies
│   └── templates/
│       ├── index.html      # Resume Coach UI
│       ├── agent.html      # Job Search Agent UI
│       ├── jobs.html       # Job Results Board UI
│       └── resume_partial.html
├── resume/
│   ├── render.py           # CLI resume renderer
│   ├── template.html       # Jinja2 + CSS resume template
│   ├── resume-base.yaml    # Master resume content (edit this)
│   ├── requirements.txt    # Resume module dependencies
│   └── overrides/          # Per-job override YAML files
└── Project-history/        # Feature specs and phase logs
```

---

## Job Sources

| Source | Method | Notes |
|---|---|---|
| LinkedIn | python-jobspy | Rate-limited; default 15 results/search |
| Indeed | python-jobspy | Rate-limited; default 15 results/search |
| Glassdoor | python-jobspy | Rate-limited; default 15 results/search |
| Google Jobs | python-jobspy | Rate-limited; default 15 results/search |
| ZipRecruiter | python-jobspy | Rate-limited; default 15 results/search |
| Himalayas | REST API | Remote-only; default 20 results |
| Arbeitnow | REST API | Remote-only; no rate limit issues |

---

## Privacy

All processing runs locally. No resume data, job preferences, session history, or LLM conversations leave your machine. Ollama serves the model from localhost. Job scraping contacts the listed job board APIs/sites directly — no intermediary service.

---

## Feature History

| Feature | Description | Status |
|---|---|---|
| F001 — Dynamic Resume | YAML → PDF pipeline with per-job overrides | Done |
| F002 — Resume Builder Web App | Flask + Ollama coaching UI with inline editing | Done |
| F003 — Job Scraper Agent | 7-source scraper + LLM scoring + review board | Done |
| F004 — LLM Persistent Memory | Session logging, fact extraction, memory injection | Done |
| F005 — Job Preferences & Filters | Persistent sidebar with source toggles and saved prefs | Done |
