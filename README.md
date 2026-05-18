# AI Recruiting Shortlist Assistant

A beginner-friendly Python MVP for locally ranking `.txt` resumes against a job description.

Recruiter-assist disclaimer: This tool is an aid for organizing and summarizing candidate information. It should not be the sole basis for employment decisions. Review outputs for accuracy, bias, legal compliance, and job-relatedness before using them.

## What It Does

1. Reads `input/job_description.txt`
2. Reads `.txt` resumes from `input/resumes/`
3. Scores each resume using this 100-point model:
   - Required skills match: 30
   - Relevant experience: 25
   - Industry/domain fit: 15
   - Tools/platforms match: 10
   - Seniority alignment: 10
   - Location/work authorization/availability fit: 10
4. Writes:
   - `output/ranked_shortlist.csv`
   - `output/candidate_report.md`
   - `output/outreach_messages.md`

## Setup

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Edit `.env` and add your `OPENAI_API_KEY`.

The app can run without an API key. If no key is found, it uses a simple local keyword-based scoring fallback. The `openai` package is only needed when you want AI-assisted scoring.

## Usage

1. Paste the job description into `input/job_description.txt`.
2. Add one or more `.txt` resumes to `input/resumes/`.
3. Run:

```bat
run.bat
```

Or:

```bat
python src\main.py
```

## Notes

- `.txt` resumes are supported first for this MVP.
- PDF and DOCX parsing are intentionally not included yet.
- The outputs are recruiter-assist drafts and should be reviewed before use.
