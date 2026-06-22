# F001 — Dynamic Resume — Phases

**Feature code:** F001
**Spec:** [F001-dynamic-resume-spec.md](F001-dynamic-resume-spec.md)
**Created:** 2026-04-30
**Status:** Done

---

## Phase 1 — Project Setup & Dependencies
**Status:** Done
**Goal:** Create folder structure, install dependencies, and scaffold the render script entry point.

### Tasks
- [x] Create `resume/` folder with subfolders: `overrides/`, `output/`
- [x] Create `requirements.txt` with: `playwright`, `jinja2`, `pyyaml`
- [x] Install dependencies (`pip install -r requirements.txt` + `playwright install chromium`)
- [x] Scaffold `render.py` with CLI arg parsing (`--job [slug]`, default = base only)
- [x] Confirm: `python render.py --help` runs without error

---

## Phase 2 — Base Resume YAML
**Status:** Done
**Goal:** Populate `resume-base.yaml` with all content from the current PDF resume — every section, every bullet, every entry.

### Tasks
- [x] Create `resume/resume-base.yaml`
- [x] Fill `meta` section (name, contact, LinkedIn)
- [x] Fill `title` line
- [x] Fill `summary` paragraphs (3 paragraphs as list)
- [x] Fill `expertise` list (12 items)
- [x] Fill `experience` entries (6 jobs, all bullets)
- [x] Fill `education` entries (2 degrees)
- [x] Fill `certifications` list (10 items)
- [x] Fill `skills` categories (5 categories with inline item strings)
- [x] Fill `languages` line
- [x] Review YAML for accuracy against original PDF

---

## Phase 3 — HTML/CSS Template
**Status:** Done
**Goal:** Build `template.html` as a Jinja2 template that reproduces the exact visual design of the current resume.

### Tasks
- [x] Create `resume/template.html` with Jinja2 syntax for all sections
- [x] Header: name (large, navy `#1a2e4a`) + contact right-aligned
- [x] Title line: teal `#2d7c9a`, medium weight
- [x] Summary paragraphs block
- [x] Expertise two-column grid
- [x] Section headers: all-caps, teal, bold
- [x] Experience entries: company/location left + dates right, job title on gray bar, bullets
- [x] Education entries: bold degree, inline institution + location + year
- [x] Certifications two-column grid
- [x] Skills: bold category label + inline comma list
- [x] Languages line
- [x] CSS: font (Open Sans / Calibri fallback), spacing, margins, bullet `▪` marker
- [x] Visual check: HTML renders with all 9 content checks passing

---

## Phase 4 — Render Script
**Status:** Done
**Goal:** Complete `render.py` so one command merges base + override YAML, renders the template, and exports a submission-ready PDF.

### Tasks
- [x] Load `resume-base.yaml`
- [x] If `--job` flag given: load `overrides/resume-[slug].yaml` and deep-merge over base
- [x] Render merged data into `template.html` via Jinja2
- [x] Launch Playwright headless Chromium, load rendered HTML
- [x] Export PDF to `output/resume-[slug].pdf` (or `output/resume-base.pdf`)
- [x] Set PDF page size to Letter, margins to match original
- [x] Print confirmation: `✓ Exported output/resume-[slug].pdf`
- [x] Handle missing override file gracefully (clear error message)

---

## Phase 5 — Override System & Validation
**Status:** Done
**Goal:** Prove the override system works end-to-end with a real test override, and validate PDF output is submission-ready.

### Tasks
- [x] Create `overrides/resume-sample.yaml` with a test title + summary swap + trimmed expertise list
- [x] Run `python render.py --job sample` and confirm PDF generates correctly
- [x] Run `python render.py` (no flag) and confirm base PDF generates correctly
- [x] Missing override error handling confirmed (clear error message, exit code 1)
- [x] Document usage in `resume/README.md`
