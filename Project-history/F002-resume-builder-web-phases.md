# F002 — Resume Builder Web App — Phases

**Feature code:** F002
**Spec:** [F002-resume-builder-web-spec.md](F002-resume-builder-web-spec.md)
**Created:** 2026-04-30
**Status:** In Progress

---

## Phase 1 — Flask Setup & Folder Structure
**Status:** Done
**Goal:** Add Flask to the project, create the webapp folder, and confirm a basic server runs at localhost:5000.

### Tasks
- [x] Create `webapp/` folder with subfolders: `static/`, `templates/`
- [x] Add `flask` and `requests` to `resume/requirements.txt`
- [x] Install new dependencies in `.venv`
- [x] Create `webapp/app.py` — minimal Flask app with a single `/` route
- [x] Create `webapp/templates/index.html` — full UI shell (modal, two panels, toolbar)
- [x] Confirm: Flask test client returns 200, modal + both panels present

---

## Phase 2 — Two-Panel UI & Startup Modal
**Status:** Done
**Goal:** Build the full visual layout — startup modal, Q&A panel (left), live resume panel (right) — with no AI yet.

### Tasks
- [x] Startup modal: "Start Fresh" / "Load My Resume" — centered overlay on page load
- [x] Two-panel CSS layout: Q&A chat panel (left 38%) + resume panel (right 62%)
- [x] Q&A panel: chat bubbles, scrollable, textarea + Enter to send, Send button
- [x] Resume panel: white page on grey background, scrollable
- [x] `GET /load` route — reads `resume-base.yaml`, renders `resume_partial.html`, returns JSON
- [x] Resume panel populates on "Load My Resume" — 12/12 content checks pass
- [x] "Start Fresh" → first Q&A question displayed as AI bubble
- [x] Save + Export PDF toolbar buttons (placeholders, wired in Phase 5)
- [x] Resume CSS scoped in index.html — all rp-* classes, editable hover/focus styles
- [x] `data-field` attributes on all text nodes — ready for Phase 4 contenteditable

---

## Phase 3 — Ollama Q&A Engine
**Status:** Done
**Goal:** Wire up Ollama so the AI conducts the Q&A interview and converts raw answers into structured resume content.

### Tasks
- [x] Confirm Ollama installed and `llama3.1:8b` pulled
- [x] `GET /api/start` — resets state, returns first question
- [x] `POST /api/chat` — state machine: stores answers, advances questions, detects section completion
- [x] Section definitions: 9 sections, predefined questions, loop support for experience/education
- [x] `polish_section()` — Ollama polish prompts for summary, expertise, experience bullets, certs, skills
- [x] `apply_section()` — maps polished data into resume_data dict
- [x] `render_section_html()` — renders just the updated section div
- [x] JS: `/api/start` on startFresh, POST to `/api/chat`, `handleUpdate()` replaces section in DOM, flash animation
- [x] State machine test: meta section Q&A completes correctly, data written, section_idx advances

---

## Phase 4 — Live Resume Updates & Inline Editing
**Status:** Done
**Goal:** Resume panel updates section by section as Q&A progresses, and every text node is editable inline.

### Tasks
- [x] `handleUpdate()` replaces section div via `outerHTML`, appends if section not yet present
- [x] Resume sections wrapped in `<div id="section-[key]">` for targeted DOM replacement
- [x] `makeEditable(root)` scoped to optional root element, `data-editable` guard prevents duplicate listeners
- [x] `blur` handler: strips `▪` prefix, calls `setNestedValue(resumeState, field, value)`
- [x] `handleUpdate()` calls `makeEditable(el)` immediately after DOM swap — new content editable right away
- [x] Yellow flash on section update (900ms fade)
- [x] "Load My Resume" path: `resumeState` initialized from `/load` response `data` field
- [x] `/api/chat` responses include `state_data` — JS syncs `resumeState` on every section completion
- [x] `/load` returns `{html, data}` — both verified in test

---

## Phase 5 — Save & Export PDF
**Status:** Done
**Goal:** Wire up the Save and Export PDF buttons so the full workflow completes end to end.

### Tasks
- [x] `POST /api/save` route — receives in-memory resume state from JS, deep-merges with base YAML, writes `resume-base.yaml`
- [x] [ Save ] button → POST to `/api/save` → success toast: "Resume saved"
- [x] `GET /export` route — reads current resume state from session, calls `render.py`, streams PDF back as download
- [x] [ Export PDF ] button → GET `/export` → browser downloads `resume-[slug].pdf`
- [x] Test full "Start Fresh" flow: Q&A → resume builds → edit inline → Save → Export PDF → open PDF and verify
- [x] Test full "Load My Resume" flow: loads YAML → edit inline → Save → Export PDF → verify changes in PDF
- [x] Confirm Save and Export are fully independent (saving does not trigger export and vice versa)
