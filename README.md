# AI Recruiting Shortlist Assistant

A local command-line MVP that helps recruiters compare `.txt`, `.pdf`, and `.docx` resumes against a job description and produce a ranked shortlist, candidate report, and outreach message drafts.

Recruiter-assist disclaimer: This tool is an aid for organizing and summarizing candidate information. It should not be the sole basis for employment decisions. Review outputs for accuracy, bias, legal compliance, and job-relatedness before using them.

## Project Overview

AI Recruiting Shortlist Assistant reads a job description from `input/job_description.txt`, scans resumes from `input/resumes/`, scores each candidate against a defined rubric, and writes recruiter-ready outputs to the `output/` folder.

The MVP supports `.txt`, `.pdf`, and `.docx` resumes. If `OPENAI_API_KEY` is available in `.env`, the app uses OpenAI-assisted scoring. If no API key is present, it falls back to simple local keyword-based scoring so the workflow remains easy to test.

## Features

- Local command-line workflow with no web app required.
- `.txt`, `.pdf`, and `.docx` resume parsing from `input/resumes/`.
- Job description parsing from `input/job_description.txt`.
- 100-point scoring rubric:
  - Required skills match: 30
  - Relevant experience: 25
  - Industry/domain fit: 15
  - Tools/platforms match: 10
  - Seniority alignment: 10
  - Location/work authorization/availability fit: 10
- Recommendation tiers:
  - 80-100: Strong Match
  - 60-79: Possible Match
  - 0-59: Weak Match
- Demo-ready CSV and Markdown outputs.
- Recruiter notes, submission summaries, and draft outreach messages.
- `sample_candidate.txt` is ignored if present, so demo data does not pollute live scoring.

## Installation

Install dependencies with `uv`:

```bat
uv venv
uv pip install -r requirements.txt
```

Create your local environment file:

```bat
copy .env.example .env
```

Edit `.env` and add your API key:

```text
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4o-mini
```

The OpenAI package is only required for AI-assisted scoring. The app can still run without an API key using the built-in heuristic fallback.

## Usage

### Command-Line Workflow

1. Paste the job description into:

```text
input/job_description.txt
```

2. Add candidate resumes as `.txt`, `.pdf`, or `.docx` files:

```text
input/resumes/candidate1.txt
input/resumes/candidate2.pdf
input/resumes/candidate3.docx
```

3. Run the assistant:

```bat
uv run python src/main.py
```

You can also use:

```bat
run.bat
```

### Web Demo

The project also includes a lightweight Flask web demo for local use. It lets a user paste a job description, upload multiple `.txt`, `.pdf`, or `.docx` resumes at once, click **Analyze Candidates**, and view ranked candidate results in the browser.

Install dependencies:

```bat
uv pip install -r requirements.txt
```

Start the web demo:

```bat
uv run python src/web_app.py
```

Open:

```text
http://127.0.0.1:5000
```

This web demo supports multiple .txt, .pdf, and .docx resume uploads. API keys stay on the server and are never sent to the browser.

## Output Files

The app regenerates these files on each run:

```text
output/ranked_shortlist.csv
output/candidate_report.md
output/outreach_messages.md
```

### `ranked_shortlist.csv`

A spreadsheet-friendly ranked shortlist with candidate name, resume file, total score, match tier, submission summary, recruiter notes, and category-level scores.

### `candidate_report.md`

A recruiter-facing Markdown report with an overall submission summary, ranked shortlist table, candidate score breakdowns, strengths, gaps, and follow-up notes.

### `outreach_messages.md`

Draft outreach content for candidates who are worth contacting. Weak matches are clearly marked with no outreach recommended for the current role.

## Demo Scenario

The `demo/` folder contains a ready-to-run sample scenario for an Enterprise Customer Success Manager role at a B2B SaaS platform serving HR and recruiting teams.

Demo files:

```text
demo/
  job_description.txt
  sample_resumes/
    candidate1.txt
    candidate2.txt
    candidate3.txt
  sample_outputs/
    ranked_shortlist.csv
    candidate_report.md
    outreach_messages.md
```

To run the demo, copy the sample job description and resumes into the live input folder, then run the assistant:

```powershell
Copy-Item demo\job_description.txt input\job_description.txt -Force
Copy-Item demo\sample_resumes\*.txt input\resumes\ -Force
uv run python src/main.py
```

After the run, compare the regenerated files in `output/` with the reference files in `demo/sample_outputs/`.

## Project Structure

```text
demo/
  job_description.txt
  sample_resumes/
  sample_outputs/
input/
  job_description.txt
  resumes/
output/
src/
  main.py
  web_app.py
  parse_resumes.py
  score_candidates.py
  generate_outputs.py
  prompts.py
requirements.txt
.env.example
run.bat
```

## Notes

- This is an MVP intended for local recruiter-assist workflows.
- PDF parsing uses `pypdf`; DOCX parsing uses `python-docx`.
- Scanned image PDFs may not produce useful text unless OCR is added later.
- Outputs should be reviewed before being shared with candidates or hiring teams.
