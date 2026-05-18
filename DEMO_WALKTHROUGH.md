# AI Recruiting Shortlist Assistant Demo Walkthrough

## What the Tool Does

AI Recruiting Shortlist Assistant is a local command-line tool that compares candidate resumes against a job description and produces recruiter-ready shortlist materials.

It reads a job description, parses candidate resumes, scores each candidate against a structured hiring rubric, and generates:

- A ranked shortlist CSV
- A candidate report
- Draft outreach messages

## Who It Is For

This MVP is designed for staffing agencies, recruiting firms, talent teams, and solo recruiters who need a faster way to organize candidate submissions before recruiter review.

It is especially useful for teams that receive multiple resumes for the same role and want a consistent first-pass comparison.

## Business Problem It Solves

Recruiters often spend significant time manually reviewing resumes, comparing candidates, writing summaries, and preparing outreach. This tool reduces that repetitive work by turning raw job and resume text into structured, reviewable outputs.

The goal is not to replace recruiter judgment. The goal is to give recruiters a faster starting point so they can focus on relationship building, quality review, and client communication.

## Step-by-Step Demo Instructions

1. Open the project folder.

2. Review the sample job description:

```text
demo/job_description.txt
```

3. Review the sample resumes:

```text
demo/sample_resumes/
```

4. Copy the demo files into the live input folder:

```powershell
Copy-Item demo\job_description.txt input\job_description.txt -Force
Copy-Item demo\sample_resumes\*.txt input\resumes\ -Force
```

5. Run the assistant:

```powershell
uv run python src/main.py
```

6. Open the generated outputs:

```text
output/ranked_shortlist.csv
output/candidate_report.md
output/outreach_messages.md
```

7. Compare the generated results with the reference outputs:

```text
demo/sample_outputs/
```

## Talking Points for a Staffing or Recruiting Firm Owner

- This tool creates a consistent first-pass screening workflow for every role.
- It helps recruiters move faster from resume intake to shortlist presentation.
- It produces materials that are easy to review, edit, and share internally.
- It keeps the recruiter in control by positioning AI as an assistant, not a decision-maker.
- It can help standardize candidate summaries across recruiters and clients.
- It is local and simple, making it easy to demo before investing in a larger web application.

## Suggested Next Improvements

- Add a web dashboard for uploading jobs and resumes.
- Add PDF and DOCX demo resume files.
- Add configurable scoring rubrics by role type.
- Add client-ready shortlist export formatting.
- Add candidate comparison tables.
- Add recruiter feedback controls to improve future scoring.
- Add applicant tracking system integrations.
- Add audit logs and stronger compliance review features.
