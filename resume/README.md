# Dynamic Resume

## Files

| File | Purpose |
|---|---|
| `resume-base.yaml` | Master resume — all content. Edit this to update your core resume. |
| `template.html` | Layout and CSS. Edit this to change design, fonts, colors, or spacing. |
| `overrides/resume-[slug].yaml` | Per-job tailoring. Only include keys you want to change from base. |
| `output/resume-[slug].pdf` | Generated PDFs — ready to submit. |

## How to render

```bash
# Activate the virtual environment first
source .venv/bin/activate

# Render base resume
python render.py

# Render tailored version for a specific job
python render.py --job aws-cloud-engineer

# Custom output filename
python render.py --job aws-cloud-engineer --out "Alex_Zare_AWS_Engineer.pdf"
```

## How to tailor for a new job

1. Copy `overrides/resume-sample.yaml` to `overrides/resume-[job-slug].yaml`
2. Edit only the sections relevant to that role (title, summary, expertise — at minimum)
3. Run `python render.py --job [job-slug]`
4. Find the PDF in `output/`

## What can be overridden

Any key from `resume-base.yaml` can be overridden. Common changes per job:
- `title` — adjust the headline for the role
- `summary` — reframe the narrative for the target position
- `expertise` — trim or reorder to highlight the most relevant skills
- `experience[n].bullets` — swap bullets to front-load the most relevant achievements
