# F004 — LLM Persistent Memory System

**Feature code:** F004
**Created:** 2026-04-30
**Status:** Spec Ready — Awaiting Approval

---

## Problem

The resume coaching session (F002) has no memory between sessions. Every time the app is restarted, the model starts from zero — it doesn't know what was discussed, what was already improved, or what still needs work. The user has to re-explain context every session.

---

## Goal

Build a lightweight persistent memory layer that:
1. Logs every coaching session to disk
2. After each session, extracts key facts, completed work, and pending tasks using the LLM
3. Injects the extracted memory into the system prompt at the start of every new session
4. Gives the user a way to view and manage their memory in the UI

---

## Architecture

### Storage (3 files, all in `webapp/memory/`)

```
webapp/memory/
├── facts.json        ← persistent facts about the user, resume, and goals
├── work_log.json     ← completed and pending tasks
└── sessions/
    └── YYYY-MM-DD_HH-MM.jsonl   ← raw conversation log per session
```

**facts.json** — things that remain true across sessions:
```json
{
  "updated": "2026-04-30",
  "facts": [
    "User completed AWS Cloud Institute program — do not say 'currently completing' or 'expected Sep 2025'",
    "Target roles: Cloud Solutions Architect, Senior Full Stack Developer",
    "Transitioning from construction/healthcare PM background into cloud/tech"
  ]
}
```

**work_log.json** — task tracker:
```json
{
  "updated": "2026-04-30",
  "completed": [
    "Rewrote summary paragraph 2 to past tense (2026-04-30)"
  ],
  "pending": [
    "Update AWS Cloud Institute entry in Experience section to reflect completion",
    "Strengthen certifications section — remove (in-progress) labels for obtained certs"
  ]
}
```

**sessions/YYYY-MM-DD_HH-MM.jsonl** — raw log, one JSON object per line:
```
{"role": "user", "content": "rephrase this section...", "ts": "2026-04-30T14:23:01"}
{"role": "assistant", "content": "Here is the rewrite...", "ts": "2026-04-30T14:23:08"}
```

---

## How It Works

### Session start
1. Read `facts.json` and `work_log.json`
2. Inject into the coaching system prompt as a **Memory** block:
```
=== MEMORY FROM PAST SESSIONS ===
Facts:
- User completed AWS Cloud Institute — do not say 'currently completing'
- Target role: Cloud Solutions Architect

Pending work:
- Update AWS Experience entry to reflect completion
- Fix certifications (in-progress) labels

Recently completed:
- Rewrote summary paragraph 2 to past tense
=== END MEMORY ===
```

### During session
- Every turn appended to `sessions/YYYY-MM-DD_HH-MM.jsonl` in real time
- Each log entry includes a `ts` (ISO timestamp) field — must be added at write time since `state['chat_history']` does not currently store timestamps
- `state['chat_history']` continues working as-is for in-session context
- Memory source of truth for injection is `state['resume_data']` (not the `resume_state` global in app.py — that is a legacy duplicate)

### Session end (triggered by user clicking "End Session")
- Single LLM extraction call sent to Qwen3 (reuses existing `extract_json()` helper in app.py):
```
Here is today's coaching session:
[full session log]

Extract and return JSON with:
1. "new_facts": any new facts about the user, resume, or goals discovered today
2. "completed": tasks completed in this session (be specific)
3. "pending": tasks mentioned or identified but not yet done
4. "remove_pending": any pending tasks from before that are now done

Only include items that are genuinely new or resolved. Do not duplicate existing entries.
```
- Extraction result merged into `facts.json` and `work_log.json`

> **Note on auto-trigger:** Do NOT use `beforeunload` + `fetch()` — browsers cancel async requests on tab close. If auto-trigger is desired in a future phase, use `navigator.sendBeacon()` which is fire-and-forget safe. Primary trigger is the "End Session" button.

---

## UI Changes

### Left panel — coaching mode
- Add a **"Memory"** button in the `.qa-header` (next to the panel title text)
- Clicking it opens a small drawer/sidebar showing:
  - **Facts** — what the coach knows about you
  - **Pending** — what's left to do
  - **Completed** — what's been done
- Each item has an ✕ to delete it manually
- An "Add fact" input to manually add something the model should always know

### Toolbar
- Add an **"End Session"** button (alongside Save and Export PDF)
- Triggers `POST /api/memory/end-session` → extraction call → updates files → shows "Memory updated" toast

---

## Backend Routes (new in F004)

| Route | Method | Purpose |
|---|---|---|
| `/api/memory` | GET | Return current `facts.json` + `work_log.json` combined |
| `/api/memory/fact` | POST | Add a fact manually `{fact: "..."}` |
| `/api/memory/fact/<idx>` | DELETE | Remove a fact by index |
| `/api/memory/pending/<idx>` | DELETE | Remove a pending item by index |
| `/api/memory/end-session` | POST | Trigger LLM extraction, merge into memory files |

---

## Phases

1. **Storage & logging** — create `webapp/memory/` structure, write session log in real time
2. **Injection** — read facts + work_log at session start, inject into coaching system prompt
3. **Extraction** — "End Session" button triggers LLM extraction call, merges results into files
4. **Memory UI** — memory drawer in left panel with view/edit/delete per item

---

## Design Decisions

| Decision | Choice | Rejected alternative | Reason |
|---|---|---|---|
| Storage format | JSON files | SQLite, vector DB | Simple, human-readable, no extra dependencies |
| Extraction timing | On "End Session" click | After every message | Extraction adds latency; once per session is enough |
| Extraction model | qwen3:32b (same model) | Separate smaller model | No extra model needed; context is already small |
| Session log format | JSONL (one object per line) | Single JSON array | Append-friendly — no need to read/rewrite the whole file |
| Memory injection | Prepended block in system prompt | Separate retrieval step (RAG) | Resume sessions are short; full injection always fits in context |

---

## What This Enables

- Coach remembers across sessions: "you told me last week you already graduated"
- Pending task list persists: "you still haven't updated your certifications section"
- Work log builds up over time — shows what's been improved
- Portable: `webapp/memory/` folder can be backed up or moved to another machine

---

## Out of Scope (future)

- Vector search / RAG over session history (not needed at this scale)
- Multi-user memory (single-user app)
- Cloud sync of memory files
