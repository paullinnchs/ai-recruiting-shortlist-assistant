import json
import os
import re
from collections import Counter

from prompts import SCORING_SYSTEM_PROMPT, SCORING_USER_PROMPT


SCORING_WEIGHTS = {
    "Required skills match": 30,
    "Relevant experience": 25,
    "Industry/domain fit": 15,
    "Tools/platforms match": 10,
    "Seniority alignment": 10,
    "Location/work authorization/availability fit": 10,
}

SCORE_KEY_ALIASES = {
    "Required skills match": {
        "required skills match",
        "required_skills_match",
        "required skills",
        "skills match",
        "skills",
    },
    "Relevant experience": {
        "relevant experience",
        "relevant_experience",
        "experience",
        "work experience",
    },
    "Industry/domain fit": {
        "industry/domain fit",
        "industry domain fit",
        "industry_domain_fit",
        "industry fit",
        "domain fit",
        "industry",
        "domain",
    },
    "Tools/platforms match": {
        "tools/platforms match",
        "tools platforms match",
        "tools_platforms_match",
        "tools match",
        "platforms match",
        "tools",
        "platforms",
    },
    "Seniority alignment": {
        "seniority alignment",
        "seniority_alignment",
        "seniority",
        "level alignment",
    },
    "Location/work authorization/availability fit": {
        "location/work authorization/availability fit",
        "location work authorization availability fit",
        "location_work_authorization_availability_fit",
        "location",
        "work authorization",
        "authorization",
        "availability",
        "location fit",
    },
}

SKILL_TERMS = {
    "python",
    "javascript",
    "typescript",
    "java",
    "sql",
    "postgresql",
    "mysql",
    "fastapi",
    "django",
    "flask",
    "react",
    "node",
    "aws",
    "azure",
    "gcp",
    "docker",
    "kubernetes",
    "git",
    "api",
    "apis",
    "machine learning",
    "data",
}

TOOL_TERMS = {
    "aws",
    "azure",
    "gcp",
    "docker",
    "kubernetes",
    "postgresql",
    "mysql",
    "snowflake",
    "salesforce",
    "hubspot",
    "github",
    "gitlab",
    "jira",
}

SENIORITY_TERMS = {
    "intern",
    "junior",
    "associate",
    "mid",
    "senior",
    "lead",
    "principal",
    "manager",
    "director",
}

LOCATION_TERMS = {
    "remote",
    "hybrid",
    "onsite",
    "united states",
    "u.s.",
    "us",
    "visa",
    "authorized",
    "authorization",
    "available",
    "availability",
}


def score_all_candidates(job_description: str, resumes: list[dict]) -> list[dict]:
    load_env_file()
    use_openai = bool(os.getenv("OPENAI_API_KEY"))

    scored = []
    for resume in resumes:
        if use_openai:
            try:
                result = score_with_openai(job_description, resume)
            except Exception as exc:
                result = score_with_heuristics(job_description, resume)
                result["notes"] = f"OpenAI scoring failed; used local heuristic. Error: {exc}"
        else:
            result = score_with_heuristics(job_description, resume)
            result["notes"] = "No OPENAI_API_KEY found; used local heuristic scoring."

        result["file_name"] = resume["file_name"]
        scored.append(result)

    return sorted(scored, key=lambda item: item["total_score"], reverse=True)


def score_with_openai(job_description: str, resume: dict) -> dict:
    from openai import OpenAI

    client = OpenAI()
    response = client.chat.completions.create(
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        messages=[
            {"role": "system", "content": SCORING_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": SCORING_USER_PROMPT.format(
                    job_description=job_description,
                    resume_text=resume["text"],
                ),
            },
        ],
        response_format={"type": "json_object"},
        temperature=0.2,
    )
    data = json.loads(response.choices[0].message.content)
    return normalize_score(data, resume["candidate_name"])


def score_with_heuristics(job_description: str, resume: dict) -> dict:
    job_text = job_description.lower()
    resume_text = resume["text"].lower()

    required_skills = extract_matching_terms(job_text, resume_text, SKILL_TERMS)
    tools = extract_matching_terms(job_text, resume_text, TOOL_TERMS)
    seniority = extract_matching_terms(job_text, resume_text, SENIORITY_TERMS)
    location = extract_matching_terms(job_text, resume_text, LOCATION_TERMS)

    job_keywords = important_words(job_description)
    resume_keywords = important_words(resume["text"])
    keyword_overlap = set(job_keywords) & set(resume_keywords)

    scores = {
        "Required skills match": proportional_score(required_skills, extract_terms(job_text, SKILL_TERMS), 30),
        "Relevant experience": min(25, len(keyword_overlap) * 2),
        "Industry/domain fit": min(15, domain_fit_score(job_text, resume_text, keyword_overlap)),
        "Tools/platforms match": proportional_score(tools, extract_terms(job_text, TOOL_TERMS), 10),
        "Seniority alignment": proportional_score(seniority, extract_terms(job_text, SENIORITY_TERMS), 10),
        "Location/work authorization/availability fit": proportional_score(location, extract_terms(job_text, LOCATION_TERMS), 10),
    }

    strengths = build_strengths(required_skills, tools, seniority, location)
    gaps = build_gaps(job_text, resume_text)
    total = sum(scores.values())

    return normalize_score(
        {
            "candidate_name": resume["candidate_name"],
            "scores": scores,
            "total_score": total,
            "strengths": strengths,
            "gaps": gaps,
            "recommendation": recommendation_for(total),
            "outreach_message": make_outreach_message(resume["candidate_name"], strengths),
        },
        resume["candidate_name"],
    )


def normalize_score(data: dict, fallback_name: str) -> dict:
    scores = data.get("scores", {})
    normalized_scores = {}
    for category, max_points in SCORING_WEIGHTS.items():
        value = find_score_value(scores, category)
        normalized_scores[category] = max(0, min(max_points, int(round(float(value)))))

    total = sum(normalized_scores.values())
    return {
        "candidate_name": data.get("candidate_name") or fallback_name,
        "scores": normalized_scores,
        "total_score": total,
        "strengths": ensure_list(data.get("strengths")),
        "gaps": ensure_list(data.get("gaps")),
        "recommendation": recommendation_for(total),
        "outreach_message": data.get("outreach_message") or make_outreach_message(fallback_name, []),
    }


def find_score_value(scores: dict, category: str) -> float:
    if not isinstance(scores, dict):
        return 0

    if category in scores:
        return safe_number(scores[category])

    normalized_lookup = {normalize_score_key(key): value for key, value in scores.items()}
    for alias in SCORE_KEY_ALIASES[category]:
        normalized_alias = normalize_score_key(alias)
        if normalized_alias in normalized_lookup:
            return safe_number(normalized_lookup[normalized_alias])

    return 0


def normalize_score_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value).lower()).strip()


def safe_number(value) -> float:
    if isinstance(value, dict):
        for key in ("score", "points", "value"):
            if key in value:
                return safe_number(value[key])

    try:
        return float(value)
    except (TypeError, ValueError):
        match = re.search(r"\d+(\.\d+)?", str(value))
        return float(match.group(0)) if match else 0


def extract_terms(text: str, terms: set[str]) -> set[str]:
    return {term for term in terms if term in text}


def extract_matching_terms(job_text: str, resume_text: str, terms: set[str]) -> set[str]:
    return extract_terms(job_text, terms) & extract_terms(resume_text, terms)


def proportional_score(matches: set[str], expected: set[str], max_points: int) -> int:
    if not expected:
        return max_points if matches else int(max_points * 0.6)
    return round(max_points * (len(matches) / len(expected)))


def important_words(text: str) -> Counter:
    words = re.findall(r"[a-zA-Z][a-zA-Z+#.-]{2,}", text.lower())
    stop_words = {
        "and",
        "the",
        "for",
        "with",
        "this",
        "that",
        "are",
        "you",
        "our",
        "will",
        "from",
        "have",
        "has",
        "job",
        "role",
        "candidate",
        "experience",
    }
    return Counter(word for word in words if word not in stop_words)


def domain_fit_score(job_text: str, resume_text: str, overlap: set[str]) -> int:
    domain_terms = {
        "saas",
        "healthcare",
        "finance",
        "fintech",
        "recruiting",
        "retail",
        "education",
        "security",
        "analytics",
        "marketplace",
        "enterprise",
    }
    domain_matches = extract_matching_terms(job_text, resume_text, domain_terms)
    return len(domain_matches) * 5 + min(10, len(overlap))


def build_strengths(skills: set[str], tools: set[str], seniority: set[str], location: set[str]) -> list[str]:
    strengths = []
    if skills:
        strengths.append(f"Matches required skills: {', '.join(sorted(skills))}.")
    if tools:
        strengths.append(f"Matches tools/platforms: {', '.join(sorted(tools))}.")
    if seniority:
        strengths.append(f"Seniority signals found: {', '.join(sorted(seniority))}.")
    if location:
        strengths.append(f"Location/work availability signals found: {', '.join(sorted(location))}.")
    return strengths or ["Resume contains some relevant job-related keywords."]


def build_gaps(job_text: str, resume_text: str) -> list[str]:
    missing_skills = sorted(extract_terms(job_text, SKILL_TERMS) - extract_terms(resume_text, SKILL_TERMS))
    missing_tools = sorted(extract_terms(job_text, TOOL_TERMS) - extract_terms(resume_text, TOOL_TERMS))
    gaps = []
    if missing_skills:
        gaps.append(f"Missing or unclear required skills: {', '.join(missing_skills)}.")
    if missing_tools:
        gaps.append(f"Missing or unclear tools/platforms: {', '.join(missing_tools)}.")
    return gaps or ["No major gaps detected by the MVP scorer."]


def recommendation_for(total_score: int) -> str:
    if total_score >= 80:
        return "Strong Match"
    if total_score >= 60:
        return "Possible Match"
    return "Weak Match"


def make_outreach_message(candidate_name: str, strengths: list[str]) -> str:
    first_name = candidate_name.split()[0] if candidate_name else "there"
    reason = strengths[0] if strengths else "your background looks relevant to the role."
    return (
        f"Hi {first_name}, I came across your background and thought it could be a fit "
        f"for a role we are reviewing. {reason} Would you be open to a brief conversation?"
    )


def ensure_list(value) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def load_env_file(path: str = ".env") -> None:
    if not os.path.exists(path):
        return

    with open(path, "r", encoding="utf-8") as env_file:
        for line in env_file:
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
