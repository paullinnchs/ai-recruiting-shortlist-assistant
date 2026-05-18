from pathlib import Path


def read_job_description(path: str = "input/job_description.txt") -> str:
    job_path = Path(path)
    if not job_path.exists():
        raise FileNotFoundError(f"Job description not found: {job_path}")

    text = job_path.read_text(encoding="utf-8").strip()
    if not text:
        raise ValueError("input/job_description.txt is empty.")
    return text


def read_txt_resumes(folder: str = "input/resumes") -> list[dict]:
    resumes_path = Path(folder)
    resumes_path.mkdir(parents=True, exist_ok=True)

    resumes = []
    for resume_file in sorted(resumes_path.glob("*.txt")):
        if resume_file.name.lower() == "sample_candidate.txt":
            continue

        text = resume_file.read_text(encoding="utf-8").strip()
        if text:
            resumes.append(
                {
                    "file_name": resume_file.name,
                    "candidate_name": guess_candidate_name(text, resume_file.stem),
                    "text": text,
                }
            )

    return resumes


def guess_candidate_name(text: str, fallback: str) -> str:
    for line in text.splitlines():
        cleaned = line.strip()
        if cleaned:
            return cleaned[:80]
    return fallback.replace("_", " ").replace("-", " ").title()
