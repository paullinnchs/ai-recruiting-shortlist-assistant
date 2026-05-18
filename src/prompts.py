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

DISCLAIMER = (
    "Recruiter-assist disclaimer: This tool is an aid for organizing and "
    "summarizing candidate information. It should not be the sole basis for "
    "employment decisions. Review outputs for accuracy, bias, legal compliance, "
    "and job-relatedness before using them."
)
