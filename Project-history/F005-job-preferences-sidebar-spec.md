# F005 — Job Preferences & Filters Sidebar

**Status:** Done  
**Shipped:** 2026-04-30

---

## Summary

Replaced the top-mounted source card row on the Job Search Agent page (`agent.html`) with a persistent left sidebar. The sidebar contains three sections: source toggles, a saveable Job Preferences form, and a Job Filters panel. The same sidebar was also added to the Job Results page (`jobs.html`). Preferences are persisted server-side and injected into the agent's context on every search.

---

## Sidebar Sections

### 1 — Sources
- 7 toggle cards: LinkedIn, Indeed, Glassdoor, Google Jobs, ZipRecruiter, Himalayas, Arbeitnow
- Each card shows a colored dot and a note (Major boards / Remote-only / EU + Remote)
- State persisted to `localStorage` on agent page; used as board filter on jobs page
- Deselecting cards filters the jobs board to active sources only (`source IN (...)` query)

### 2 — Job Preferences
These help the agent tailor searches. Saved to `webapp/memory/job_preferences.json`.

| Field | Type | Limit |
|---|---|---|
| Job Titles | Text inputs | Up to 5 |
| Location Type | Chips | On-site · Remote · Hybrid |
| Locations – On-site | Text inputs | Up to 5 |
| Locations – Remote | Text inputs | Up to 5 |
| Employment Type | Chips | Full-time · Part-time · Contract · Internship |

- **Save Preferences** button → `POST /api/preferences`
- Loaded on page open via `GET /api/preferences`
- Injected automatically into the agent's first message as a `=== JOB PREFERENCES ===` block

### 3 — Job Filters
Stored as preferences (agent uses them). Date Posted also filters the jobs board.

| Field | Type | Notes |
|---|---|---|
| Date Posted | Radio | Any time / Past month / Past week / Past 24 hours — filters `date_scraped` in DB |
| Experience Level | Checkboxes | Internship / Entry / Associate / Mid-Senior / Director / Executive |
| Minimum Salary | Select | $40k – $200k+ |

- Experience Level and Salary auto-save on change via `POST /api/preferences/filters`

---

## Backend Changes

### app.py
- `PREFS_FILE = MEMORY_DIR / "job_preferences.json"` — created on first run
- `GET /api/preferences` — returns full prefs JSON
- `POST /api/preferences` — merges incoming fields into prefs file
- `POST /api/preferences/filters` — updates only `experience_levels` and `min_salary`
- `_format_preferences()` — formats prefs as a readable agent context block
- `api_agent_chat` — injects `_format_preferences()` block into the first user message

### db.py
- `get_jobs` source filter now supports comma-separated values → `source IN (a,b,c)`
- Added `days_ago` filter: `date_scraped >= (today - N days)`
