# Build Plan — AI-resume-job

Master feature index. One entry per feature. All detail lives in `Project-history/` — follow the links.

**Feature status:** `Planned` | `Spec Ready` | `Approved` | `In Progress` | `Done` | `On Hold`
**Phase status:** `Pending` | `Active` | `Done`

---

<!-- 
  Claude: append new entries at the bottom in the format below.
  Never remove or reorder entries.
  Update Status and Progress lines as work advances.
  Add the Phases link only after the phases file is created.
-->

## F001 — Dynamic Resume
**Status:** Done
**Summary:** YAML-driven resume with HTML/CSS template and one-command PDF export — content and style independently editable by user or AI agent.
**Spec:** [F001-dynamic-resume-spec.md](Project-history/F001-dynamic-resume-spec.md)
**Phases:** [F001-dynamic-resume-phases.md](Project-history/F001-dynamic-resume-phases.md)
**Progress:** All 5 phases complete

## F002 — Resume Builder Web App
**Status:** Done
**Summary:** Single-page Flask web app with AI-guided Q&A (via Ollama local LLM) that builds a resume section by section, with inline contenteditable editing and one-click PDF export.
**Spec:** [F002-resume-builder-web-spec.md](Project-history/F002-resume-builder-web-spec.md)
**Phases:** [F002-resume-builder-web-phases.md](Project-history/F002-resume-builder-web-phases.md)
**Progress:** All 5 phases complete

## F003 — Job Scraper Agent & Review Board
**Status:** Done
**Summary:** AI agent (Ollama with tool calling) takes job criteria from the user via chat, scrapes LinkedIn/Indeed/Glassdoor/Google/ZipRecruiter/Himalayas/Arbeitnow in parallel, scores results by relevance, and presents them in a filterable review board where the user can save, dismiss, or apply.
**Spec:** [F003-job-scraper-agent-spec.md](Project-history/F003-job-scraper-agent-spec.md)
**Phases:** [F003-job-scraper-agent-phases.md](Project-history/F003-job-scraper-agent-phases.md)
**Progress:** All 5 phases complete

## F004 — LLM Persistent Memory System
**Status:** Done
**Summary:** Persistent memory layer for the resume coach — logs sessions to disk, extracts facts and task lists via LLM after each session, injects memory into the system prompt on next session so the coach always knows what was discussed, what's done, and what's pending.
**Spec:** [F004-llm-persistent-memory-spec.md](Project-history/F004-llm-persistent-memory-spec.md)
**Phases:** [F004-llm-persistent-memory-phases.md](Project-history/F004-llm-persistent-memory-phases.md)
**Progress:** All 5 phases complete

## F005 — Job Preferences & Filters Sidebar
**Status:** Done
**Summary:** Left sidebar on the Job Search Agent and Job Results pages — source toggle cards (moved from top), a saveable Job Preferences form (titles, location types, locations, employment type), and a Job Filters panel (date posted, experience level, salary). Preferences persist server-side and are injected into the agent's context on every search.
**Spec:** [F005-job-preferences-sidebar-spec.md](Project-history/F005-job-preferences-sidebar-spec.md)
**Phases:** —
**Progress:** Shipped in one pass 2026-04-30

---

<!--
ENTRY TEMPLATE:

## F[NNN] — [Feature Name]
**Status:** Planned
**Summary:** [One sentence — what it does and why it matters.]
**Spec:** [F[NNN]-[slug]-spec.md](Project-history/F[NNN]-[slug]-spec.md)
**Phases:** —
**Progress:** Phases 1–4 done · Phase 5 active

When phases are created and work begins, update to:

## F[NNN] — [Feature Name]
**Status:** In Progress — Phase [X] of [N]
**Summary:** [unchanged]
**Spec:** [F[NNN]-[slug]-spec.md](Project-history/F[NNN]-[slug]-spec.md)
**Phases:** [F[NNN]-[slug]-phases.md](Project-history/F[NNN]-[slug]-phases.md)
**Progress:** Phase 1 done · Phase 2 active · Phase 3–4 pending
-->
