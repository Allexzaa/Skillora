# F001 — Dynamic Resume — Spec

**Feature code:** F001
**Slug:** dynamic-resume
**Status:** Approved
**Created:** 2026-04-30
**Approved:** 2026-04-30
**Phases file:** [F001-dynamic-resume-phases.md](F001-dynamic-resume-phases.md)

---

## Problem

A static resume (Word/PDF) can't be quickly tailored per job — every edit risks breaking layout, and an AI agent can't reliably change specific sections without corrupting the file. We need a resume where content, style, and structure are all independently editable by both the user and an AI agent, with reliable PDF export on demand.

---

## Proposed Approach

**Two-file model: base data + per-job override, rendered to PDF.**

```
resume-base.yaml              ← master content (never auto-edited)
overrides/
  resume-[job-slug].yaml      ← per-job patches (summary, bullets, skills)
template.html                 ← layout + CSS (mirrors current design)
render.py                     ← merges base + override → PDF
```

**Render flow:**
```
resume-base.yaml ──┐
                   ├──→ render.py → Jinja2 → HTML (in memory) → Playwright → resume-[slug].pdf
override.yaml   ───┘
```

One command: `python render.py --job aws-solutions-architect`  
Output: `output/resume-aws-solutions-architect.pdf`

---

## Architecture

### File layout

```
resume/
├── resume-base.yaml              ← full master resume
├── render.py                     ← render script
├── template.html                 ← Jinja2 template + CSS
├── overrides/
│   └── resume-[job-slug].yaml    ← per-job patches
└── output/
    └── resume-[job-slug].pdf     ← generated PDFs
```

### resume-base.yaml structure (mapped from your current resume)

```yaml
meta:
  name: Alex Zare
  location: Portland, OR
  phone: 408-515-0654
  email: alex.zare99@gmail.com
  linkedin: LinkedIn Profile
  linkedin_url: "https://..."

title: "Cloud Solutions Architect | Full Stack Developer | Senior Project Manager"

summary:
  - >
    Motivated and resourceful early-career Cloud Solutions Architect and Full Stack
    Developer with a strong foundation in AWS architecture, infrastructure as code (IaC),
    and cloud-native application development...
  - >
    Currently completing an intensive, project-based curriculum with the AWS Cloud
    Institute (expected Sep 2025)...
  - >
    Passionate about cloud innovation...

expertise:
  - Cloud Architecture & Infrastructure Design
  - Cloud-Native Full Stack Development
  - Microservices Architecture & RESTful APIs
  - Infrastructure as Code
  - CI/CD Pipeline Implementation
  - Cloud Operations & Cost Optimization
  - AI/ML Integration & Prompt Engineering
  - DevOps & Automation Practices
  - System Implementation & Performance Tuning
  - Technical Documentation & Knowledge Transfer
  - Cross-Functional & Multilingual Collaboration
  - Stakeholder Engagement & Communication

experience:
  - company: Amazon Web Services
    location: Remote
    title: Cloud Solutions Architect Training – AWS Cloud Institute
    dates: "2025 – Present (Expected Completion: Sep 2025)"
    bullets:
      - Completing a structured 9-month, hands-on program...
      - Built a secure serverless onboarding application...
      - Developed a serverless scheduling application...
      - Architecting and developing cloud-native platforms...

  - company: Pence Contractors
    location: Oregon & California
    title: Senior Project Engineer
    dates: "2023 – 2024"
    bullets:
      - Quickly mastered school construction regulations...
      - Led budget creation, schedule drafting...
      - Facilitated meetings with architects, clients...

  - company: TCG Core Group
    location: Milpitas, CA
    title: Senior Project Engineer / Project Manager
    dates: "2019 – 2022"
    bullets:
      - Oversaw residential and hospital projects for Stanford and Google ($100K–$5M).
      - Drafted project schedules, estimates, and contracts...
      - Selected subcontractors and suppliers...

  - company: Holland Partner Group
    location: Oakland, CA
    title: Project Coordinator
    dates: "2017 – 2019"
    bullets:
      - Coordinated inspections, submittals, and construction reports...
      - Maintained safety compliance and managed punch list corrections...
      - Served as liaison among superintendents, subcontractors, and PMs...

  - company: Independent Projects
    location: DC, MD, VA
    title: Project Developer
    dates: "2015 – 2017"
    bullets:
      - Supported real estate investors through permitting, budgeting...
      - Worked on residential and light commercial projects...

  - company: US Army Medical Materiel Agency
    location: Fort Detrick, MD
    title: Project Manager, Imaging Devices
    dates: "2015 – 2016"
    bullets: []

education:
  - degree: M.S. in Construction Management
    institution: California State University
    location: East Bay, CA
    year: "2018"
  - degree: B.S. in Mechanical/Biomedical Engineering
    institution: University of Tennessee
    location: Knoxville, TN
    year: "2015"

certifications:
  - "Cloud Practitioner – AWS, 2025"
  - "Practitioner – AWS 2025 (in-progress)"
  - "Developer Associate – AWS 2025 (in-progress)"
  - "Solutions Architect (Associate) – AWS 2025 (in-progress)"
  - "Cloud Architect – AWS 2025 (in-progress)"
  - "OSHA 30 HR Certificate – Summit Training Source, 2021"
  - "Intermediate Systems Acquisition (PM Level II) – DAU, 2016"
  - "Fundamentals of Systems Acquisition Management (PM Level I) – DAU, 2016"
  - "Introduction to Earned Value Management – PMI, 2016"
  - "Cost Analysis – DAU, 2016"

skills:
  - category: "Cloud & AWS Services"
    items: "AWS Lambda, Amazon API Gateway, Amazon S3, Amazon DynamoDB, AWS IAM, Amazon CloudWatch, Amazon Textract, Amazon Rekognition, AWS Step Functions, AWS Amplify, AWS Cognito (intro), Amazon Bedrock (intro), Amazon SageMaker (intro), AWS EventBridge (intro), AWS Systems Manager, AWS Secrets Manager, AWS CLI, AWS SAM, Serverless Framework, AWS CDK (intro), Amazon RDS (intro), Amazon Route 53 (intro)"
  - category: "Project Tools"
    items: "Microsoft Project, Procore, SharePoint, Bluebeam Revu, GCPay"
  - category: "DevOps & Development Tools"
    items: "Git, GitHub, GitHub Actions, RESTful APIs, Postman, JSON/YAML, CI/CD (conceptual), Infrastructure as Code (IaC), Serverless Architecture, VS Code, AWS Amplify CLI"
  - category: "Frontend & Backend Technologies"
    items: "React, JavaScript, Python (introductory), HTML, CSS, Node.js (basic), Flask (basic)"
  - category: "Additional"
    items: "Kiro Studio, Firebase Studio, PartyRock (Generative AI prototyping), Lucidchart, draw.io, Visual Studio Code, Figma (basic), Markdown (technical writing), Solution Architecture Design, AWS Well-Architected Framework, UML Diagramming, Technical Documentation Standards"

languages: "Persian (Native) | English (Full Professional) | Arabic (Elementary) | French (Elementary)"
```

### Per-job override file (overrides/resume-[slug].yaml)

Only includes keys that differ from base. Render script deep-merges: override wins on any key present.

```yaml
# overrides/resume-aws-cloud-engineer.yaml
title: "Cloud Solutions Architect | AWS Engineer | DevOps Practitioner"

summary:
  - "Tailored opening paragraph for this role..."

experience:
  - company: Amazon Web Services   # matched by company name
    bullets:
      - "Rewritten bullet emphasizing the most relevant project..."
      - "..."

expertise:
  - Cloud Architecture & Infrastructure Design
  - CI/CD Pipeline Implementation
  - DevOps & Automation Practices
  # (trimmed to most relevant 8–10 for this role)
```

---

## Design Spec (from current resume)

Matching your existing style exactly:

| Element | Style |
|---|---|
| Name | Large (~32px), dark navy (`#1a2e4a`), bold |
| Contact line | Right-aligned next to name, small gray text |
| Title line | Medium (~16px), teal (`#2e7d9e`), normal weight |
| Section headers | Caps, teal (`#2e7d9e`), ~13px, bold, left-aligned |
| Company + location | Left-aligned, small caps/regular |
| Dates | Right-aligned, same row as company |
| Job title bar | Bold, on light gray background bar |
| Bullets | Small square `▪` marker, body text |
| Expertise grid | Two equal columns |
| Certifications | Two equal columns |
| Skills | Bold category label + inline comma list |
| Font | Clean sans-serif (matching: Calibri or Open Sans) |
| Page 2 header | Name left, page + contact right |

---

## Open Questions

All answered:
- ✅ **Override model:** Base file + per-job override files
- ✅ **Design:** Match current resume (teal headers, gray title bars, two-column grids)
- ✅ **Export:** PDF only — submission-ready

---

## Out of Scope

- No web UI or editor — editing is direct file editing or AI agent
- No plain-text / ATS export in this phase
- No auto-submission to job boards in this phase
- No cloud storage or sync in this phase
