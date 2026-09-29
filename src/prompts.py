SCORING_SYSTEM_PROMPT = """
You are helping a recruiter compare a resume against a job description.
Return practical, evidence-based scoring only. Do not infer protected-class
attributes. Keep the analysis job-related.
"""

SCORING_USER_PROMPT = """
Score this resume against the job description using exactly these categories:
- Required skills match: 30
- Relevant experience: 25
- Industry/domain fit: 15
- Tools/platforms match: 10
- Seniority alignment: 10
- Location/work authorization/availability fit: 10

Return valid JSON with:
candidate_name, scores, total_score, strengths, gaps, recommendation,
outreach_message.

The scores object must use these exact keys:
"Required skills match", "Relevant experience", "Industry/domain fit",
"Tools/platforms match", "Seniority alignment",
"Location/work authorization/availability fit".

Job description:
{job_description}

Resume:
{resume_text}
"""

CRITERIA_SYSTEM_PROMPT = """
You convert a job description that has already passed a readiness review into a
normalized list of hiring criteria for a recruiting team.

Extract only requirements the job description actually states. Do not invent,
infer, generalize, or add requirements. Responsibilities, company descriptions,
benefits, and culture language are not candidate criteria unless the job
description states them as a requirement.
"""

CRITERIA_USER_PROMPT = """
Extract the hiring criteria from the job description below.

Return valid JSON with exactly these keys:
- "job_title": the role title as written, or an empty string.
- "must_have": list of criterion objects the job description states as required.
- "preferred": list of criterion objects the job description states as preferred,
  desired, a plus, or nice to have.

Each criterion object has exactly these keys:
- "text": the requirement, stated plainly as one verifiable qualification.
- "kind": one of "experience", "ksa", "education", "certification", "domain",
  "tool", "logistics".
- "source_excerpt": the exact words copied from the job description that state
  this requirement. Copy them verbatim. Do not paraphrase.

Rules:
- One requirement per criterion.
- If the job description does not label a requirement as preferred, it is must-have.
- Every criterion must have a verbatim source_excerpt.

Job description:
{job_description}
"""

EVALUATION_SYSTEM_PROMPT = """
You assess one candidate's written information against a fixed list of hiring
criteria for a recruiting team. You never make a hiring decision.

Use only what the candidate information states. Do not infer skills, employers,
credentials, tenure, or any other fact the text does not state. Keep the analysis
job-related and do not consider protected-class attributes.

Absence of evidence is not evidence of absence. When the candidate information
does not address a criterion, the verdict is UNKNOWN, never DOES_NOT_MEET.
"""

EVALUATION_USER_PROMPT = """
Assess the candidate against every criterion below.

Return valid JSON with exactly one key:
- "assessments": one object per criterion, each with exactly these keys:
  - "criterion_id": the id shown for the criterion.
  - "verdict": one of "MEETS", "PARTIALLY_MEETS", "DOES_NOT_MEET", "UNKNOWN".
  - "evidence_quote": the exact words copied from the candidate information that
    support the verdict. Copy them verbatim. Empty string when the verdict is UNKNOWN.
  - "rationale": one sentence explaining the verdict.

Verdict rules:
- MEETS: the candidate information clearly shows the criterion is satisfied.
- PARTIALLY_MEETS: the information shows the criterion is partly satisfied.
- DOES_NOT_MEET: the information explicitly shows the criterion is not satisfied.
- UNKNOWN: the information does not say either way.
- Any verdict other than UNKNOWN requires a verbatim evidence_quote that is
  about this specific criterion. A statement about something else does not
  prove this criterion is or is not satisfied.
- When a criterion names a type of experience, adjacent or general experience
  does not MEET it. Use PARTIALLY_MEETS or UNKNOWN when equivalence is uncertain.

Criteria:
{criteria}

Candidate information:
{resume_text}
"""

DISCLAIMER = (
    "Recruiter-assist disclaimer: This tool is an aid for organizing and "
    "summarizing candidate information. It should not be the sole basis for "
    "employment decisions. Review outputs for accuracy, bias, legal compliance, "
    "and job-relatedness before using them."
)
