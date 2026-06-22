# Job Sources Research — Scraping & API Options

Researched: 2026-04-30

## Top 5 Job Sources

### 1. JobSpy — Open-Source Python Library (Best Overall)
- **Method:** `pip install jobspy` — no API key needed
- **Sources:** LinkedIn, Indeed, Glassdoor, Google Jobs, ZipRecruiter — all simultaneously
- **Output:** Pandas DataFrame → CSV or DB ready
- **Legal:** Permissible under hiQ v. LinkedIn ruling (public data); may violate individual platform ToS
- **Link:** https://github.com/speedyapply/JobSpy

### 2. Indeed — Direct Web Scrape
- **Method:** Web scrape (no official public API since 2022)
- **Volume:** Largest job database in the world
- **Ease:** High — minimal rate limiting reported in 2026
- **Link:** https://www.scraperapi.com/web-scraping/job-scraping/

### 3. Google Jobs via SerpApi — Official API
- **Method:** Official REST API (`/search?engine=google_jobs`)
- **Why:** Aggregates Indeed, LinkedIn, ZipRecruiter, Workday in one call
- **Cost:** Free tier (100 searches/month), then paid
- **Link:** https://serpapi.com

### 4. Himalayas — Free Public API
- **Method:** Official REST API, no key required
- **Focus:** Remote jobs only
- **Catch:** Must link back to their site in the UI
- **Link:** https://himalayas.app

### 5. Arbeitnow — Free Job Board API
- **Method:** Official REST API — completely free, no auth required
- **Focus:** Europe + English-speaking remote roles
- **Why:** Zero friction, good for testing ingestion pipeline
- **Link:** https://www.arbeitnow.com/blog/job-board-api

---

## Recommendation

**Start with JobSpy** — one library hits 5 sources simultaneously and outputs clean structured data ideal for a job-matching pipeline.  
**Add SerpApi** if a more stable/paid source is needed later.

---

## Legal Notes
- Scraping publicly available job data is generally legal under the CFAA (hiQ Labs v. LinkedIn, 2022)
- ToS violations can create breach-of-contract liability — check `robots.txt` before scraping
- GDPR applies to EU job listings containing personal data
- Circumventing technical access controls may invoke DMCA
