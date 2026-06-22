# F003 — Job Scraper Agent & Review Board

**Status:** Spec Ready — awaiting approval
**Created:** 2026-04-30
**Reviewed:** 2026-04-30 (architecture audit complete)

---

## Goal

A two-page web app where the user tells an AI agent (running locally via Ollama) what kind of jobs they want. The agent extracts structured search parameters, calls multiple job APIs/scrapers in parallel, batch-scores all results for relevance in a single LLM call, and populates a review board where the user can skim, save, or dismiss jobs.

---

## Architecture Overview

```
User (Browser)
    │
    ├── Page 1: /agent  ──────────→ Chat UI (job intake)
    │       │
    │       ▼
    │   Flask /api/agent/chat ────→ Ollama (tool-calling model, see §Model)
    │                                   │
    │              ┌─────────────────────┼─────────────────────┐
    │              ▼                     ▼                     ▼
    │      Tool: search_jobs()   Tool: search_remote_jobs()  Tool: search_eu_jobs()
    │              │                     │                     │
    │       JobSpy (LinkedIn,      Himalayas API          Arbeitnow API
    │       Indeed, Glassdoor,     (free, no key)         (free, no key)
    │       Google, ZipRecruiter)
    │              │
    │              └──→ Batch score ALL jobs in ONE Ollama call
    │                              │
    │                       SQLite jobs.db (scored + stored)
    │
    └── Page 2: /jobs  ──────────→ Review Board (cards + filters)
            │
            └── Actions: Save · Dismiss · Open URL · Export CSV
```

---

## Pages

### Page 1 — `/agent` (Job Search Chat)

- Chat interface (vanilla CSS, same style as F002)
- **Source selector panel** shown before the chat starts (see detail below)
- User describes the role they want in natural language
- Agent asks 2–3 clarifying questions (role, location/remote, seniority, industry)
- Agent calls only the tools whose sources are enabled in the selector
- Batch-scores all results in one Ollama call after scraping completes
- On completion: "Found 47 jobs — [View Results →]" link to `/jobs`

#### Source Selector Panel

Displayed as a row of toggleable cards above the chat input, visible at all times. Each card shows the source name, logo/icon, and an enabled/disabled state. Default: all enabled.

| Source | Default | Notes shown to user |
| --- | --- | --- |
| LinkedIn | ON | May require proxy on large searches |
| Indeed | ON | Most reliable, no rate limits |
| Glassdoor | ON | May be slow |
| Google Jobs | ON | Best for broad searches |
| ZipRecruiter | ON | US/Canada only |
| Himalayas | ON | Remote jobs only |
| Arbeitnow | ON | EU + remote roles |

- Toggling a source off removes it from the agent's tool call — the agent only calls `search_jobs()` for active JobSpy sources, and skips `search_remote_jobs()` / `search_eu_jobs()` if Himalayas / Arbeitnow are off.
- Selected sources are passed as a `sources` array in the `/api/agent/chat` POST body.
- The panel persists its state in `localStorage` so selections survive page refresh.

### Page 2 — `/jobs` (Review Board)

- Card grid: job title, company, location, source badge, match score (1–10), date found
- Top filter bar: Source | Status (New / Saved / Dismissed) | Min Score | Job Type | Remote only
- Per-card actions: **Save** (green), **Dismiss** (grey), **Details** (expand description), **Apply** (opens original URL)
- Pagination (25 per page)
- Export button → downloads saved jobs as CSV

---

## Backend Routes

> **Note:** All F003 routes are namespaced under `/agent` or `/api/agent/` to avoid collision with F002's existing `/api/chat`, `/api/save`, `/export` routes.

| Route | Method | Purpose |
| --- | --- | --- |
| `/agent` | GET | Serve job search chat UI |
| `/api/agent/chat` | POST | Ollama agent with tool calling; body includes `message` + `sources[]` array |
| `/jobs` | GET | Serve review board |
| `/api/jobs` | GET | Return jobs JSON (filters via query params) |
| `/api/job/<id>/save` | POST | Mark job saved |
| `/api/job/<id>/dismiss` | POST | Mark job dismissed |
| `/api/export/jobs` | GET | Stream CSV of saved jobs |

**Removed:** `/api/search` (was listed but never triggered by anything — redundant with tool calling flow).

---

## AI Agent — Model Selection

**`qwen3:32b` is NOT currently installed.** The Ollama server's installed models do not include it.

Available models that support tool/function calling (from current server):

| Model | Tool Calling | Size | Notes |
| --- | --- | --- | --- |
| `qwen3-next:80b` | Yes (Qwen3 family) | 80B | Best balance for this task |
| `gemma3:27b` | Yes | 27B | Lighter, fast |
| `ministral-3:8b` | Yes | 8B | Fastest, lower quality |

**Recommended:** `qwen3-next:80b` — same family as the F002 model, strong tool calling, available now.

**Before Phase 1:** confirm which model to use. Update `AGENT_MODEL` constant in `app.py`.

---

## AI Agent — Tool Calling Design

**New function required:** The existing `call_ollama()` in `app.py:171` has no `tools` parameter support. A new `call_ollama_with_tools(messages, tools)` function must be written that passes the `tools` array to the Ollama `/api/chat` endpoint.

**Tools registered with the agent:**

```python
search_jobs(
    query: str,           # e.g. "senior software engineer"
    location: str,        # e.g. "Toronto" or "remote"
    job_type: str,        # fulltime | parttime | contract | internship
    remote: bool,
    results_wanted: int   # default 20 per source
)
# Calls JobSpy → LinkedIn, Indeed, Glassdoor, Google, ZipRecruiter

search_remote_jobs(query: str)
# Calls Himalayas public REST API — remote jobs only, no key needed

search_eu_jobs(query: str)
# Calls Arbeitnow public REST API — EU + remote, no key needed
```

**Agent conversation state** (separate from F002's `state` dict):

```python
agent_state = {
    "messages":        [],       # full message history for multi-turn chat
    "search_criteria": {},       # extracted: query, location, job_type, remote
    "active_sources":  [],       # e.g. ["linkedin", "indeed", "himalayas"] — set from UI
    "search_done":     False,
}
```

**Agent loop:**

1. User sends message → `/api/agent/chat` with `{"message": "...", "sources": ["linkedin", "indeed", ...]}`
2. Flask reads `sources` array and registers **only the tools for enabled sources** with Ollama
3. Ollama decides: ask clarifying question OR call a tool
4. If tool call: Flask executes it, returns result to Ollama as a tool-response message
5. After all enabled tools return: Flask sends all job results to Ollama in **one batch scoring call** (plain `call_ollama()`)
6. Batch scoring returns a JSON list: `[{"url": "...", "score": 7}, ...]`
7. Jobs + scores written to SQLite; agent responds with summary count + `/jobs` link

---

## Batch Scoring Design

Scoring is **not** done per-job (that would require 100–150 Ollama calls). Instead, after all scrapers return, all jobs are sent to Ollama in one prompt:

```
Given these job search criteria: {criteria}

Score each job below from 1–10 for relevance. Return ONLY valid JSON:
[{"url": "<url>", "score": <int>}, ...]

Jobs:
1. Title: ... | Company: ... | Location: ... | URL: ...
2. ...
```

This is one LLM call regardless of job count.

---

## Rate Limits & Scraping Constraints

> Read this before setting `results_wanted` or running searches in a loop.

### JobSpy — Platform-by-Platform

| Source | Rate Limit | Hard Cap | Restrictions | Safe Default |
| --- | --- | --- | --- | --- |
| **LinkedIn** | Blocks ~page 10 per IP (~100–200 jobs) | ~1,000 | Proxies strongly recommended; `linkedin_fetch_description=True` multiplies requests | `results_wanted=15` |
| **Indeed** | None reported as of 2026 | ~1,000 | Cannot combine `hours_old` with `job_type`/`is_remote` | `results_wanted=25` |
| **Glassdoor** | Aggressive blocking (same severity as LinkedIn) | ~1,000 | Requires `country_indeed` param for geo filter | `results_wanted=15` |
| **Google Jobs** | Unconfirmed | ~1,000 | Query must exactly match browser search syntax; generic queries return nothing | `results_wanted=20` |
| **ZipRecruiter** | Unconfirmed | ~1,000 | US/Canada only | `results_wanted=20` |

**429 response = IP blocked.** Mitigation: add `time.sleep(2)` between source calls; pass a `proxies` list for rotation if hitting limits regularly.

**Implementation note:** Run all 5 JobSpy sources via a single `scrape_jobs()` call — JobSpy handles them concurrently internally. Do not loop and call per-source manually.

---

### Himalayas API

| Limit | Value |
| --- | --- |
| Authentication | None required |
| Max jobs per request | **20** (hard cap reduced March 2025) |
| Rate limit threshold | Not publicly documented — returns **HTTP 429** when exceeded |
| Pagination | `offset` + `limit` params (browse); `page` param (search) |
| Attribution | **Mandatory** — must link back to Himalayas as original source |
| Redistribution | Prohibited — do not forward to Google Jobs, LinkedIn, Jooble, etc. |

**Safe usage:** fetch one page of 20, do not hammer in a loop. If 429 is hit, back off 60 seconds and retry once. For higher limits contact hi@himalayas.app.

---

### Arbeitnow API

| Limit | Value |
| --- | --- |
| Authentication | None required |
| Rate limit threshold | **Not publicly documented** |
| Pagination | Supported — exact params not in public docs; check `page` query param |
| Base endpoint | `https://www.arbeitnow.com/api/job-board-api` |
| Notable param | `visa_sponsorship=true/false` |
| Custom/private tier | Available for a monthly fee — contact@arbeitnow.com |

**Safe usage:** treat as unknown rate limit — add `time.sleep(1)` before calling; do not call in a tight loop. If 429 is returned, back off 60 seconds.

---

### Recommended Per-Search Caps (default config)

```python
JOBSPY_RESULTS_PER_SOURCE = 15   # conservative; raise to 25 for Indeed only
HIMALAYAS_LIMIT           = 20   # hard cap — do not exceed
ARBEITNOW_LIMIT           = 20   # conservative; exact limit unknown
DELAY_BETWEEN_SOURCES_SEC = 2    # sleep between each scraper call
```

Max jobs per full search session: ~135 (15×5 JobSpy + 20 Himalayas + 20 Arbeitnow). Well within all known limits for a single-user personal tool.

---

## Data Layer — SQLite (`webapp/jobs.db`)

```sql
CREATE TABLE jobs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    title        TEXT,
    company      TEXT,
    location     TEXT,
    job_type     TEXT,
    remote       BOOLEAN,
    description  TEXT,
    url          TEXT UNIQUE,
    source       TEXT,        -- linkedin | indeed | glassdoor | google | ziprecruiter | himalayas | arbeitnow
    date_posted  TEXT,
    date_scraped TEXT,
    match_score  INTEGER,     -- 1–10, batch-scored by Ollama
    status       TEXT DEFAULT 'new'  -- new | saved | dismissed
);
```

**Dedup:** `url TEXT UNIQUE` — SQLite rejects duplicate URLs with `INSERT OR IGNORE`, so re-running a search never creates duplicate rows.

---

## Tech Stack

| Layer | Tech | Notes |
| --- | --- | --- |
| Web framework | Flask | Already in use (F002), same `app.py` |
| Job scraping | `python-jobspy` (`pip install python-jobspy`) | LinkedIn, Indeed, Glassdoor, Google, ZipRecruiter |
| Remote jobs | Himalayas REST API | Free, no key, remote-only |
| EU/remote jobs | Arbeitnow REST API | Free, no key |
| AI agent | Ollama `qwen3-next:80b` (TBD) | Tool calling mode; confirm model before Phase 1 |
| Database | SQLite (`webapp/jobs.db`) | Python built-in `sqlite3`, no setup |
| Frontend | Vanilla CSS + Vanilla JS | Matches F002 — no Bootstrap |

---

## Phases

| # | Phase | Deliverable |
| --- | --- | --- |
| 1 | DB + Scrapers | `jobs.db` schema; JobSpy, Himalayas, Arbeitnow as callable Python functions; `/api/jobs`, `/api/job/<id>/save`, `/api/job/<id>/dismiss`, `/api/export/jobs` routes |
| 2 | Ollama Agent + Tool Calling | `call_ollama_with_tools()`; `agent_state`; `/api/agent/chat` with tool dispatch + batch scoring + DB write |
| 3 | Agent Chat UI | `/agent` page — intake chat with progress indicator, same style as F002 |
| 4 | Review Board UI | `/jobs` page — card grid, filter bar, save/dismiss/apply actions, pagination |
| 5 | Polish + Integration | Error handling, empty-state messages, CSV export, nav link from F002 home toolbar |

---

## Key Decisions & Trade-offs

| Decision | Chosen | Rejected | Why |
| --- | --- | --- | --- |
| Job scraping | JobSpy library | Custom BeautifulSoup scrapers | JobSpy handles 5 sources concurrently, maintained, output is a clean DataFrame |
| Agent tool calling | Ollama native tools | LangChain / CrewAI | No extra framework; Ollama `/api/chat` already supports tools natively |
| Storage | SQLite | Flat JSON files | Queryable, filterable, dedup via UNIQUE constraint, handles 10k+ jobs |
| Scoring | Batch (all jobs, one LLM call) | Per-job LLM calls | Per-job = 100–150 Ollama calls; batch = 1 call, same quality |
| Job dedup | `url TEXT UNIQUE` + `INSERT OR IGNORE` | Hash comparison | URLs are canonical per job; SQLite handles it natively |
| CSS framework | Vanilla CSS | Bootstrap 5 | F002 uses no Bootstrap — keep consistent, no CDN dependency |
| Route namespace | `/api/agent/chat` etc. | Reuse `/api/chat` | F002 owns `/api/chat` at `app.py:463` — collision would crash Flask |

---

## Open Questions (resolve before Phase 1)

1. **Model:** Which model to use for tool calling — `qwen3-next:80b` (quality) or `gemma3:27b` (speed)? `qwen3:32b` is not installed.
2. **Integration:** Should `/agent` be a nav link added to the F002 toolbar, or a completely standalone entry point?
3. **Job cap:** Max jobs per search — 20 per source (100 total from JobSpy + Himalayas + Arbeitnow) or user-configurable?
4. **Search history:** Should the agent persist past search criteria for re-use, or start fresh each session?

---

## Sources

- [JobSpy GitHub](https://github.com/speedyapply/JobSpy)
- [Ollama Tool Calling Docs](https://docs.ollama.com/capabilities/tool-calling)
- [Build AI Agents with Ollama Tool Calling](https://markaicode.com/build-ai-agents-ollama-tool-calling-guide/)
- [Himalayas Public API](https://himalayas.app)
- [Arbeitnow Job Board API](https://www.arbeitnow.com/blog/job-board-api)
- [Best Job APIs 2026 — Bright Data](https://brightdata.com/blog/web-data/best-job-apis)
- [Filter UI Patterns 2026](https://bricxlabs.com/blogs/universal-search-and-filters-ui)
