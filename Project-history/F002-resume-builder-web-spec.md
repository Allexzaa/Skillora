# F002 — Resume Builder Web App — Spec

**Feature code:** F002
**Slug:** resume-builder-web
**Status:** Approved
**Created:** 2026-04-30
**Approved:** 2026-04-30
**Phases file:** [F002-resume-builder-web-phases.md](F002-resume-builder-web-phases.md)

---

## Problem

The current system requires editing YAML and running CLI commands to build or update a resume. A non-technical user — or anyone who doesn't have a resume yet — has no visual entry point. We need a web UI where a user can answer plain-language questions, have a local AI turn their answers into polished resume content, and edit the result inline before exporting.

---

## Proposed Approach

A single-page Flask web app with two panels:

- **Left panel:** conversational Q&A — the AI asks questions section by section, user answers in plain language
- **Right panel:** live resume — renders and updates as each section is completed, fully editable inline via `contenteditable`

Local AI via **Ollama** handles both the question flow and turning raw answers into polished resume language. No internet or API key required.

---

## Architecture

```
Browser
┌─────────────────────────────────────────────────────┐
│  Left: Q&A chat panel    │  Right: Live resume HTML  │
│  ─────────────────────   │  ──────────────────────   │
│  AI: "What's your name?" │  [contenteditable resume] │
│  User: "Alex Zare"       │                           │
│  AI: "What's your title?"│  Updates section by       │
│  User: "Cloud Architect" │  section as Q&A completes │
│                          │                           │
│  [Export PDF] button     │                           │
└─────────────────────────────────────────────────────┘
        │                            │
        ▼                            ▼
   Flask backend              Flask backend
   /api/chat                  /api/save + /export
        │                            │
        ▼                            ▼
     Ollama                   resume-base.yaml
  (local LLM)                 + render.py → PDF
```

### Startup

On first load, a modal asks:
> **"How would you like to start?"**
> — [ Start Fresh ] &nbsp; — [ Load My Resume ]

- **Start Fresh** → blank resume panel, Q&A begins from section 1
- **Load My Resume** → `resume-base.yaml` is loaded, resume renders fully in the right panel, Q&A panel shows "Your resume is loaded — click any section to edit, or ask me to improve it."

### Q&A Flow (section by section)

The AI walks the user through the resume in order. After all answers for a section are collected, Ollama generates polished content and the resume panel updates:

```
1. Contact info      → meta block appears
2. Title / headline  → title line appears
3. Career summary    → summary paragraphs appear
4. Areas of expertise → expertise grid appears
5. Experience        → one job at a time (loop until done)
6. Education         → education entries appear
7. Certifications    → certifications list appears
8. Skills            → skills categories appear
9. Languages         → languages line appears
```

Each section: AI asks → user answers in plain English → Ollama polishes → resume section updates → AI moves to next section.

### Inline Editing

Every text node in the resume panel has `contenteditable="true"`. User can click any text at any time and edit it directly. On blur (clicking away), changes are saved to the in-memory resume state. No separate save button needed per field.

### Export

"Export PDF" button → Flask calls `render.py` → Playwright generates PDF → browser downloads it.

---

## Local AI: Ollama

**Why Ollama:** runs locally with no API key, OpenAI-compatible REST API at `localhost:11434`, fast on consumer hardware, supports GPU acceleration automatically.

**Recommended model:** `llama3.1:8b` — fast, strong instruction following, good at generating professional writing.
**Fallback model:** `mistral:7b` — slightly faster on CPU-only machines.

**Two AI tasks:**

| Task | Prompt type | Output |
|---|---|---|
| Conduct Q&A | System: "You are a resume coach. Ask one question at a time..." | Next question as plain text |
| Polish answers | System: "Convert the user's raw answer into professional resume content..." | Structured JSON (bullets, paragraphs) |

Ollama is called from Flask via HTTP (`requests` to `localhost:11434/api/chat`).

---

## Tech Stack (additions to F001)

| Component | Tool |
|---|---|
| Web server | Flask (already in mind, add to requirements) |
| Frontend | Vanilla HTML/CSS/JS — no framework needed |
| Local AI | Ollama + `llama3.1:8b` |
| AI client | `requests` (HTTP to Ollama REST API) |
| PDF export | Existing `render.py` (Playwright) |
| Resume state | In-memory Python dict → written to YAML on export |

---

## Data Flow

```
Q&A answer (plain text)
      ↓
POST /api/chat  →  Flask  →  Ollama (polish prompt)
      ↓
Structured JSON  {section: "experience", company: "...", bullets: [...]}
      ↓
JS updates resume panel (contenteditable section)
      ↓
User edits inline (optional)
      ↓
[ Save ] button → POST /api/save → Flask writes resume state to resume-base.yaml
      ↓ (independent action)
[ Export PDF ] button → GET /export → Flask calls render.py → PDF download
```

---

## Open Questions

All answered:
- ✅ **Start mode:** On load, app asks the user: "Start fresh or load your existing resume?" — fresh starts the Q&A from scratch, load pre-fills the resume panel from `resume-base.yaml` and skips straight to inline editing.
- ✅ **Save vs Export:** Two separate actions — "Save" writes back to `resume-base.yaml`, "Export PDF" generates and downloads the PDF. Neither triggers the other automatically.

---

## Out of Scope

- PDF/Word upload and parsing (future F003)
- Cloud hosting or user accounts
- Multiple resume templates (uses existing template.html from F001)
- Claude API or any paid/remote AI service
