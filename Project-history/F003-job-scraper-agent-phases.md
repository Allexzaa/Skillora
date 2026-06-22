# F003 — Job Scraper Agent & Review Board — Phase Plan

**Spec:** [F003-job-scraper-agent-spec.md](F003-job-scraper-agent-spec.md)
**Total phases:** 5
**Status:** Pending approval — do not start Phase 1 until approved

---

## Pre-flight Checklist (before Phase 1)

- [ ] Confirm Ollama model for tool calling (`qwen3-next:80b` vs `gemma3:27b`) — answer Open Question #1
- [ ] Confirm `/agent` integration with F002 toolbar or standalone — answer Open Question #2
- [ ] Confirm job cap per search — answer Open Question #3
- [ ] `pip install python-jobspy` in the project `.venv`
- [ ] Verify chosen model accepts `tools` parameter via Ollama `/api/chat` (send a test curl with a dummy tool)

---

## Phase 1 — Database & Scraper Functions

**Goal:** All job fetching works end-to-end from Python. No UI yet. Routes exist and return data.

### Files to create

- `webapp/jobs.db` — created automatically on first run via `init_db()`
- `webapp/scrapers.py` — all scraper functions isolated here, imported by `app.py`
- `webapp/db.py` — SQLite wrapper, imported by `app.py`

### Files to modify

- `webapp/app.py` — add `from db import init_db; init_db()` alongside existing `_init_memory_dirs()` (do NOT remove the F004 memory init) + 4 new routes

### Tasks

**1.1 — `webapp/scrapers.py`**

Three functions, each returns `list[dict]` with keys:
`{title, company, location, job_type, remote, description, url, source, date_posted}`

```python
def run_jobspy(query, location, job_type, remote, sources, results_per_source=15) -> list[dict]:
    # `sources` is a filtered list e.g. ["linkedin", "indeed"] — from UI, NOT from agent
    # Calls jobspy.scrape_jobs(site_name=sources, ...)
    # Converts DataFrame rows to dicts, adds source field
    # Returns list of dicts. time.sleep(2) after call.

def run_himalayas(query) -> list[dict]:
    # GET https://himalayas.app/jobs/api/search?q={query}   ← search endpoint, NOT /jobs/api
    # /jobs/api is the unfiltered browse feed and does NOT accept a q param
    # limit param not supported on search endpoint — returns default page
    # Adds time.sleep(1) after call.

def run_arbeitnow(query) -> list[dict]:
    # GET https://www.arbeitnow.com/api/job-board-api?page=1
    # Arbeitnow does not support a q/search param on the free endpoint
    # Returns all jobs from page 1 — caller filters by keyword post-fetch
    # Adds time.sleep(1) after call.
```

> **Arbeitnow note:** the free public endpoint has no keyword filter. Return all jobs from page 1
> and let the batch scorer handle relevance — do not try to pass a query param.

**1.2 — `webapp/db.py`**

```python
DB_PATH = Path(__file__).parent / "jobs.db"  # always resolves to webapp/jobs.db

def init_db() -> None          # CREATE TABLE IF NOT EXISTS jobs (...)
def insert_jobs(jobs: list[dict]) -> int   # INSERT OR IGNORE; returns count inserted
def get_jobs(filters: dict) -> tuple[list[dict], int]  # returns (rows, total_count)
def update_status(job_id: int, status: str) -> None    # 'new' | 'saved' | 'dismissed'
def export_csv() -> str        # CSV string of all status='saved' rows
```

Schema:

```sql
CREATE TABLE IF NOT EXISTS jobs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    title        TEXT,
    company      TEXT,
    location     TEXT,
    job_type     TEXT,
    remote       BOOLEAN,
    description  TEXT,
    url          TEXT UNIQUE,
    source       TEXT,
    date_posted  TEXT,
    date_scraped TEXT,
    match_score  INTEGER DEFAULT 0,
    status       TEXT DEFAULT 'new'
);
```

`get_jobs(filters)` accepted filter keys: `source`, `status`, `min_score`, `job_type`, `remote`, `page` (25 per page, server-side pagination). All filters are passed as SQL WHERE clauses — not done in JS.

**1.3 — `webapp/app.py` additions**

```python
from db import init_db

# Add alongside existing _init_memory_dirs() — do NOT replace it:
init_db()

@app.route("/api/jobs")                    # GET  — ?source=&status=&min_score=&job_type=&remote=&page=
@app.route("/api/job/<int:job_id>/save",   methods=["POST"])   # set status='saved'
@app.route("/api/job/<int:job_id>/dismiss", methods=["POST"])  # set status='dismissed'
@app.route("/api/export/jobs")             # GET  — stream CSV of saved jobs
```

> **Naming:** use `job_id` not `id` as the route parameter — `id` shadows Python's built-in.

### Done when

- From `webapp/` directory: `python -c "from scrapers import run_jobspy; print(run_jobspy('python developer', 'remote', 'fulltime', True, ['indeed'])[:1])"` returns a real job dict
- `GET /api/jobs` returns `{"jobs": [], "total": 0}` with empty DB (no crash)
- Manually insert one row into DB, then `POST /api/job/1/save` → `{"ok": true}`
- `GET /api/export/jobs` downloads a valid CSV (empty body is fine)

---

## Phase 2 — Ollama Agent with Tool Calling

**Status:** Done
**Goal:** `/api/agent/chat` has a working multi-turn agent that calls scrapers, batch-scores, and writes to DB.

### Files to create

- None

### Files to modify

- `webapp/app.py` — add `AGENT_MODEL`, `agent_state`, `call_ollama_with_tools()`, `/api/agent/chat`, `/api/agent/reset`

### Tasks

**2.1 — `AGENT_MODEL` constant**

```python
AGENT_MODEL = "qwen3-next:80b"   # NEW constant — separate from existing OLLAMA_MODEL (F002)
                                  # Do NOT change or remove OLLAMA_MODEL
```

**2.2 — `call_ollama_with_tools(messages, tools)`**

New helper — does NOT replace `call_ollama()`. Posts to `OLLAMA_URL` with `tools` array and `model=AGENT_MODEL`.

```python
def call_ollama_with_tools(messages: list, tools: list) -> tuple[str, list]:
    # Returns (content, tool_calls)
    # tool_calls is [] when model replies in plain text
    # content may be empty string when model only issues tool calls — guard before stripping <think>
    r = http.post(OLLAMA_URL, json={"model": AGENT_MODEL, "messages": messages,
                                    "tools": tools, "stream": False}, timeout=180)
    r.raise_for_status()
    msg = r.json()["message"]
    content = msg.get("content") or ""
    if content:
        content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
    tool_calls = msg.get("tool_calls") or []
    return content, tool_calls
```

**2.3 — `agent_state` dict**

```python
agent_state: dict = {
    "messages":        [],    # full Ollama message history
    "search_criteria": {},    # populated from search_jobs tool call args (see 2.5)
    "active_sources":  [],    # set from UI on each /api/agent/chat request
    "search_done":     False,
}
```

**2.4 — `/api/agent/reset` route**

```python
@app.route("/api/agent/reset", methods=["POST"])   # POST — state change, not GET
def api_agent_reset():
    global agent_state
    agent_state = {"messages": [], "search_criteria": {}, "active_sources": [], "search_done": False}
    return jsonify({"ok": True})
```

> **Note:** this route is POST, not GET — state mutations must not be GET requests.
> The UI calls this when the page loads and when "Start new search" is clicked.

**2.5 — Tool definitions (Ollama format)**

```python
MAX_TOOL_ITERATIONS = 10   # safety cap — prevents infinite tool-calling loop

# Full AGENT_TOOLS list:
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
                    "results_wanted": {"type": "integer", "default": 15}
                },
                "required": ["query", "location"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_remote_jobs",
            "description": "Search Himalayas for remote-only jobs worldwide",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_eu_jobs",
            "description": "Search Arbeitnow for EU-based and remote jobs",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"]
            }
        }
    }
]

def get_active_tools(active_sources: list[str]) -> list[dict]:
    """Return only the tool definitions relevant to the user's enabled sources."""
    jobspy_sources = {"linkedin", "indeed", "glassdoor", "google", "ziprecruiter"}
    include_jobspy    = bool(set(active_sources) & jobspy_sources)
    include_himalayas = "himalayas" in active_sources
    include_arbeitnow = "arbeitnow" in active_sources
    return [
        t for t in AGENT_TOOLS if
        (t["function"]["name"] == "search_jobs"        and include_jobspy) or
        (t["function"]["name"] == "search_remote_jobs" and include_himalayas) or
        (t["function"]["name"] == "search_eu_jobs"     and include_arbeitnow)
    ]
```

**2.6 — `/api/agent/chat` route logic**

```python
@app.route("/api/agent/chat", methods=["POST"])
def api_agent_chat():
    body    = request.get_json()
    msg     = body.get("message", "").strip()
    sources = body.get("sources", [])   # from UI source selector
    if not msg:
        return jsonify({"reply": "I didn't catch that — try again.", "done": False})

    agent_state["active_sources"] = sources
    active_tools = get_active_tools(sources)

    agent_state["messages"].append({"role": "user", "content": msg})

    all_jobs = []
    iterations = 0

    while iterations < MAX_TOOL_ITERATIONS:
        iterations += 1
        content, tool_calls = call_ollama_with_tools(agent_state["messages"], active_tools)

        if not tool_calls:
            # Model replied in plain text — end of turn
            agent_state["messages"].append({"role": "assistant", "content": content})
            break

        # Dispatch each tool call
        agent_state["messages"].append({"role": "assistant", "content": content, "tool_calls": tool_calls})

        for tc in tool_calls:
            fn   = tc["function"]["name"]
            args = tc["function"].get("arguments", {})

            if fn == "search_jobs":
                # Capture criteria from agent's own args for batch scoring later
                agent_state["search_criteria"] = args
                # Inject active JobSpy sources from UI — agent does NOT control this
                jobspy_sources = [s for s in sources if s in {"linkedin","indeed","glassdoor","google","ziprecruiter"}]
                result = run_jobspy(
                    query=args.get("query", ""),
                    location=args.get("location", "remote"),
                    job_type=args.get("job_type", "fulltime"),
                    remote=args.get("remote", False),
                    sources=jobspy_sources,
                    results_per_source=args.get("results_wanted", 15)
                )
            elif fn == "search_remote_jobs":
                result = run_himalayas(args.get("query", ""))
            elif fn == "search_eu_jobs":
                result = run_arbeitnow(args.get("query", ""))
            else:
                result = []

            all_jobs.extend(result)
            agent_state["messages"].append({
                "role": "tool",
                "name": fn,
                "content": json.dumps({"count": len(result), "sample": result[:2]})
            })

    # After all tools complete — batch score and store
    job_count = 0
    if all_jobs and not agent_state["search_done"]:
        scores = batch_score_jobs(agent_state["search_criteria"], all_jobs)
        for job in all_jobs:
            job["match_score"] = scores.get(job["url"], 0)
        from db import insert_jobs
        job_count = insert_jobs(all_jobs)
        agent_state["search_done"] = True

    final_reply = agent_state["messages"][-1]["content"] if agent_state["messages"] else ""
    return jsonify({"reply": final_reply, "done": agent_state["search_done"], "job_count": job_count})
```

**2.7 — `batch_score_jobs(criteria, jobs)` helper**

```python
def batch_score_jobs(criteria: dict, jobs: list[dict]) -> dict[str, int]:
    # Returns {url: score} dict
    # Uses call_ollama() (not tool-calling) — plain prompt + JSON response
    # If JSON parse fails → returns {} (all jobs get score=0, not a crash)
    prompt = f"""Job search criteria: {json.dumps(criteria)}

Score each job 1–10 for relevance to the criteria above.
Return ONLY valid JSON, no other text:
[{{"url": "<url>", "score": <int>}}, ...]

Jobs:
""" + "\n".join(
        f"{i+1}. Title: {j.get('title','')} | Company: {j.get('company','')} | Location: {j.get('location','')} | URL: {j.get('url','')}"
        for i, j in enumerate(jobs)
    )
    raw = call_ollama([{"role": "user", "content": prompt}])
    try:
        scored = json.loads(re.search(r"\[.*\]", raw, re.DOTALL).group())
        return {item["url"]: int(item["score"]) for item in scored}
    except Exception:
        return {}
```

### Done when

- `POST /api/agent/chat {"message": "senior Python developer, remote", "sources": ["indeed"]}` → agent asks a clarifying question (no scraping yet)
- Follow-up with location → agent calls `search_jobs`, scrapes Indeed, scores jobs, writes to DB, returns `{"done": true, "job_count": N}`
- `GET /api/jobs` returns those jobs with non-zero scores
- Sending 11 consecutive tool-triggering messages does NOT loop past 10 iterations (cap verified)
- `POST /api/agent/reset` clears `agent_state` and returns `{"ok": true}`

---

## Phase 3 — Agent Chat UI (`/agent` page)

**Goal:** Working browser UI for job intake chat. Source selector + chat panel.

### Files to create

- `webapp/templates/agent.html`

### Files to modify

- `webapp/app.py` — add `@app.route("/agent")` GET route

### Tasks

**3.1 — Layout**

Single-column full-width layout:

```
┌─────────────────────────────────────────┐
│  Toolbar: "Job Search Agent"  [/jobs →] │
├─────────────────────────────────────────┤
│  Source Selector (7 toggle cards)       │
├─────────────────────────────────────────┤
│  Chat messages area (scrollable)        │
│                                         │
├─────────────────────────────────────────┤
│  [Text input]                  [Send]   │
└─────────────────────────────────────────┘
```

**3.2 — Source selector cards**

- 7 cards in a flex row, wrap on narrow screens
- Each card: source name + one-line note + visual ON/OFF state (dark border + checkmark vs greyed)
- State saved to `localStorage` key `f003_sources`
- On load: read from `localStorage`; if absent default all ON
- On load: also validate stored sources against known list — silently drop any unknown values before sending to backend

**3.3 — Chat behaviour**

- On page load: `POST /api/agent/reset` (not GET — see Phase 2.4), then display greeting from server or hardcoded: "Hi! I'm your job search agent. Which role are you looking for?"
- User types → `POST /api/agent/chat` with `{message, sources: getActiveSources()}`
- Show animated typing indicator while awaiting response
- On `done: true`: show "✓ Found {job_count} jobs — [View Results →]" linking to `/jobs`
- On HTTP error or `{"error": ...}`: show inline error, re-enable input

**3.4 — New search button**

"Start new search" in toolbar → `POST /api/agent/reset`, clear chat DOM, scroll to top, re-enable input.

### Done when

- `/agent` loads with 7 source cards, all ON by default
- Toggling cards off and refreshing page persists state
- Typing a message → typing indicator shows → agent reply appears
- After `done: true` response, "View Results" link appears and goes to `/jobs`

---

## Phase 4 — Review Board UI (`/jobs` page)

**Goal:** Filterable, paginated card grid with save/dismiss/apply actions.

### Files to create

- `webapp/templates/jobs.html`

### Files to modify

- `webapp/app.py` — add `@app.route("/jobs")` GET route

### Tasks

**4.1 — Layout**

```
┌──────────────────────────────────────────────────┐
│ Toolbar: "Job Results"  [New Search] [Export CSV] │
├──────────────────────────────────────────────────┤
│ Filters: Source▼  Status▼  Score≥[_]  Type▼  [Remote □] │
├──────────────────────────────────────────────────┤
│ "Showing 25 of 135 jobs"                         │
├──────────────────────────────────────────────────┤
│  card grid (3–4 columns)                         │
├──────────────────────────────────────────────────┤
│  [← Prev]   Page 2 of 6   [Next →]              │
└──────────────────────────────────────────────────┘
```

**4.2 — Job card**

- Title (bold), Company, Location
- Source badge (colour-coded per source)
- Score badge: `★ 8/10` green ≥7 · yellow 5–6 · grey ≤4 · `—` if score=0
- Date posted / scraped
- Actions: **[Save]** · **[Dismiss]** · **[Details ▾]** · **[Apply ↗]**
- Details expander: inline toggle, no page reload

**4.3 — Filter bar + Pagination (server-side, consistent)**

Filters and pagination are **both server-side** — every filter change calls `GET /api/jobs` with query params and re-renders the card grid. This is the only design that works correctly: client-side filtering with server-side pagination is impossible (page 2 from the server returns unfiltered rows).

JS sends: `GET /api/jobs?source=indeed&status=new&min_score=7&job_type=fulltime&remote=true&page=1`

Filter changes always reset `page` back to 1.

Filters available:
- **Source** — multi-select (all 7 sources + "All")
- **Status** — All / New / Saved / Dismissed
- **Score ≥** — number input 1–10
- **Job Type** — All / Full-time / Part-time / Contract / Internship
- **Remote only** — checkbox

**4.4 — Save / Dismiss**

- `POST /api/job/<id>/save` → button turns green "Saved ✓"; re-fetch not needed
- `POST /api/job/<id>/dismiss` → card fades out with CSS transition, then removed from DOM
- No page reload

**4.5 — Export CSV**

"Export CSV" in toolbar → `GET /api/export/jobs` → browser downloads `saved-jobs-YYYY-MM-DD.csv`
Filename uses today's date, set server-side in `Content-Disposition` header.

**4.6 — Empty state**

If `GET /api/jobs` returns `total: 0`: show centred message "No jobs yet — [Start a search →]" linking to `/agent`. Never show a blank page or an error.

### Done when

- `/jobs` loads all scraped jobs, paginated 25 per page
- Each filter change triggers a new `GET /api/jobs` call and re-renders correctly
- Changing filter resets to page 1
- Save/Dismiss update card visually without page reload
- Export CSV downloads file with correct filename
- Empty DB shows empty state message, not an error

---

## Phase 5 — Polish & Integration

**Goal:** All edge cases handled, F002 linked, shippable.

### Tasks

**5.1 — Error handling in scrapers**

- JobSpy returns 429 or raises on any source → log warning, skip that source, continue with others (never abort the full search)
- Himalayas 429 → `time.sleep(60)`, retry once, then skip with warning
- Arbeitnow 429 → skip with warning (rate limit unknown — don't retry)
- Ollama timeout in tool-calling loop → break loop, return `{"error": "Agent timed out — try again", "done": False}`
- `batch_score_jobs` returns `{}` (JSON parse fail) → all jobs stored with `match_score=0`, search still completes

To test these branches during development: temporarily raise `requests.exceptions.HTTPError(response=MagicMock(status_code=429))` inside the scraper function, verify the warning is logged and remaining sources still run.

**5.2 — F002 toolbar integration**

Add "Job Search →" nav link to F002's `webapp/templates/index.html` toolbar, pointing to `/agent`. Match existing toolbar button style exactly.

**5.3 — Source selector unknown-value guard** (already noted in Phase 3.2 — verify it's implemented)

**5.4 — README + Build_Plan update**

- Mark F003 Done in `Build_Plan.md` (Status → Done, Progress → All 5 phases complete)
- Update `README.md` Features section and Project Status table

### Done when

- Scraper error paths tested as described in 5.1 (mock 429, verify graceful skip)
- F002 toolbar shows "Job Search →" link and it navigates correctly
- Fresh `/jobs` with empty DB shows empty state, not error
- `README.md` and `Build_Plan.md` updated

---

## Summary Table

| Phase | Name | Key files | Blocked by |
| --- | --- | --- | --- |
| 1 | DB + Scrapers | `scrapers.py`, `db.py`, `app.py` (+4 routes) | Pre-flight complete |
| 2 | Ollama Agent | `app.py` (+tool calling, scoring, agent routes) | Phase 1 |
| 3 | Agent Chat UI | `templates/agent.html`, `app.py` (+`/agent`) | Phase 2 |
| 4 | Review Board UI | `templates/jobs.html`, `app.py` (+`/jobs`) | Phase 1 only — can run in parallel with Phase 3 |
| 5 | Polish + Integration | `index.html`, `app.py`, `README.md`, `Build_Plan.md` | Phases 3 + 4 |

---

## Issues Fixed in This Review

The following architectural problems were found and corrected during the final review pass:

1. **Himalayas wrong endpoint** — `/jobs/api?q=` does not support keyword search; corrected to `/jobs/api/search?q=`
2. **Arbeitnow has no keyword filter** — free endpoint returns all jobs; batch scorer handles relevance instead
3. **Filter + pagination contradiction** — Phase 4 originally said client-side filters with server-side pagination (impossible); both are now server-side
4. **Phase 1 test command broken** — `from webapp.scrapers import ...` fails without `__init__.py`; corrected to run from `webapp/` directory
5. **Tool-calling infinite loop** — added `MAX_TOOL_ITERATIONS = 10` cap
6. **`call_ollama_with_tools` None content crash** — added `content = msg.get("content") or ""` guard
7. **`active_sources` not injected into `run_jobspy`** — made explicit: Flask injects UI sources when dispatching tool, agent does not control this
8. **`search_criteria` never populated** — now explicitly captured from `search_jobs` tool call args at dispatch time
9. **`/api/agent/reset` was GET** — changed to POST (state mutation)
10. **F004 memory init conflict** — clarified that `init_db()` must be added alongside `_init_memory_dirs()`, not replacing it; `AGENT_MODEL` is a new constant, does not change `OLLAMA_MODEL`
