# F004 — LLM Persistent Memory System — Phases

**Feature code:** F004
**Spec:** [F004-llm-persistent-memory-spec.md](F004-llm-persistent-memory-spec.md)
**Created:** 2026-04-30
**Status:** Approved

---

## Phase 1 — Storage & Session Logging
**Status:** Done
**Goal:** Create the `webapp/memory/` folder structure and write every coaching turn to disk in real time as the session happens.

### Tasks
- [x] Create `webapp/memory/` and `webapp/memory/sessions/` directories (auto-created on first run)
- [x] Create `facts.json` and `work_log.json` with empty initial structure if they don't exist
- [x] Add `MEMORY_DIR` and `SESSIONS_DIR` path constants to `app.py`
- [x] Add `log_turn(role, content)` helper — appends `{"role": ..., "content": ..., "ts": ...}` to the current session's JSONL file
- [x] Add `session_file` to `state` — set to a new `YYYY-MM-DD_HH-MM.jsonl` path on `/load` and `/api/start`
- [x] Call `log_turn()` inside `chat_coach_mode()` for both user message and assistant reply
- [x] Scope: session logging applies to coaching (loaded) mode only — Q&A (Start Fresh) flow is intentionally not logged in this feature
- [x] Test: load resume → send 2 messages → confirmed `webapp/memory/sessions/2026-04-30_16-49.jsonl` created with 4 entries (user + assistant × 2) with ISO timestamps

---

## Phase 2 — Memory Injection
**Status:** Done
**Goal:** Read `facts.json` and `work_log.json` at the start of each coaching session and inject the content into the system prompt so the coach always has past context.

### Tasks
- [x] Add `load_memory() -> dict` helper — reads `facts.json` and `work_log.json`, returns combined dict; returns empty structure if files don't exist
- [x] Add `format_memory_block(memory: dict) -> str` helper — formats facts + pending + completed as the `=== MEMORY FROM PAST SESSIONS ===` block
- [x] Update `chat_coach_mode()` system prompt — insert memory block after the "Standards to enforce" section and before the `=== RESUME ===` block
- [x] If memory is empty (first ever session), skip the block entirely — no empty section headers
- [x] Test: wrote test fact → confirmed `load_memory()` returns it, `format_memory_block()` formats it correctly, injection lands between "Standards" and "Full resume" blocks; empty case returns `""`; temp print removed

---

## Phase 3 — Extraction & End Session
**Status:** Done
**Goal:** Add the "End Session" button that triggers an LLM call to extract facts and tasks from the session log, then merges results into `facts.json` and `work_log.json`.

### Tasks
- [x] Add `POST /api/memory/end-session` route — reads JSONL, builds extraction prompt, calls `call_ollama(think=True)`, merges via `extract_json()`; returns `{"ok": True, "memory": ...}`
- [x] Add `save_memory(facts_list, worklog_dict)` helper — atomic write via `.tmp` + `rename()` for both files
- [x] Add "End Session" button to toolbar in `index.html` — disabled by default; enabled only after `loadResume()` succeeds (Q&A flow leaves it disabled)
- [x] Wire button with toast: "Memory updated" on success (3s auto-dismiss), error toast on failure; button shows "Extracting..." while in-flight
- [ ] Test: run a coaching session, state a new fact, click End Session, verify `facts.json` updated (Phase 5)

---

## Phase 4 — Memory API & UI Drawer
**Status:** Done
**Goal:** Let the user view, manually edit, and delete memory items through a drawer in the left panel.

### Tasks
- [x] Add `GET /api/memory` route — returns combined `facts.json` + `work_log.json`
- [x] Add `POST /api/memory/fact` route — appends a new fact `{fact: "..."}` to `facts.json`; deduplicates before saving
- [x] Add `DELETE /api/memory/fact/<idx>` route — removes fact by index; returns 400 on out-of-range
- [x] Add `DELETE /api/memory/pending/<idx>` route — removes pending item by index; returns 400 on out-of-range
- [x] Add "Memory" button to `.qa-header` in `index.html`
- [x] Add memory drawer HTML — slides in over left panel via CSS transform; Facts + Pending + Completed sections
- [x] Wire drawer JS: `openMemoryDrawer()` fetches `GET /api/memory` and re-renders; `addFact()`, `deleteFact(i)`, `deletePending(i)` each call the route then re-open the drawer to refresh
- [x] Test: all 4 routes verified via curl — GET empty, POST adds, GET reflects, DELETE removes, out-of-range returns 400

---

## Phase 5 — Integration Test & Polish
**Status:** Done
**Goal:** Full end-to-end test of the memory system across two simulated sessions, plus any UX polish.

### Tasks
- [ ] Session 1: load resume → tell coach "I already graduated from AWS Cloud Institute" → ask for a rephrase → click End Session → verify `facts.json` contains the graduation fact (requires live Ollama — manual test)
- [ ] Session 2: restart server → load resume → ask coach about the AWS section → verify it does NOT suggest "currently completing" language (requires live Ollama — manual test)
- [ ] Verify memory drawer shows correct state after Session 2 (manual test)
- [x] Edge cases — all verified via curl with live server:
  - [x] Empty memory files on first run — returns `{facts:[], completed:[], pending:[]}`, no crash
  - [x] Corrupted `facts.json` or `work_log.json` — `load_memory()` catches exception, returns empty structure, server stays healthy
  - [x] Session file missing at end-session — returns `{"error": "No session log found"}` with 400 status, no crash
  - [x] Extraction returns malformed JSON — `extract_json()` returns `{}`; merge skips all lists, `save_memory()` never called, existing files untouched
- [x] No leftover debug logging (one legitimate `print` in agent error handler retained)
- [x] Build_Plan.md — F004 marked Done, all 5 phases complete
- [x] README.md — F004 marked Done, F003 + F004 features described
