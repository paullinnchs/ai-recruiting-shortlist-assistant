import csv
from pathlib import Path

from prompts import DISCLAIMER
from score_candidates import SCORING_WEIGHTS


def write_outputs(scored_candidates: list[dict], output_dir: str = "output") -> None:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    write_ranked_shortlist(scored_candidates, output_path / "ranked_shortlist.csv")
    write_candidate_report(scored_candidates, output_path / "candidate_report.md")
    write_outreach_messages(scored_candidates, output_path / "outreach_messages.md")


def write_ranked_shortlist(scored_candidates: list[dict], path: Path) -> None:
    fieldnames = [
        "Rank",
        "Candidate Name",
        "Resume File",
        "Total Score",
        "Match Tier",
        "Submission Summary",
        "Recruiter Notes",
        *SCORING_WEIGHTS.keys(),
    ]

    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        for rank, candidate in enumerate(scored_candidates, start=1):
            row = {
                "Rank": rank,
                "Candidate Name": candidate["candidate_name"],
                "Resume File": candidate["file_name"],
                "Total Score": f"{candidate['total_score']}/100",
                "Match Tier": candidate["recommendation"],
                "Submission Summary": submission_summary(candidate),
                "Recruiter Notes": recruiter_notes(candidate),
            }
            row.update(candidate["scores"])
            writer.writerow(row)


def write_candidate_report(scored_candidates: list[dict], path: Path) -> None:
    lines = [
        "# AI Recruiting Shortlist Assistant - Candidate Report",
        "",
        DISCLAIMER,
        "",
        "## Submission Summary",
        "",
        summary_line(scored_candidates),
        "",
    ]

    if not scored_candidates:
        lines.append("No resumes were found in `input/resumes/`.")
    else:
        lines.extend(["## Ranked Shortlist", ""])
        lines.extend(markdown_summary_table(scored_candidates))
        lines.extend(["", "## Candidate Details", ""])

        for rank, candidate in enumerate(scored_candidates, start=1):
            lines.extend(
                [
                    f"### {rank}. {candidate['candidate_name']}",
                    "",
                    f"**Match Tier:** {candidate['recommendation']}",
                    "",
                    f"**Total Score:** {candidate['total_score']}/100",
                    "",
                    f"**Submission Summary:** {submission_summary(candidate)}",
                    "",
                    f"**Recruiter Notes:** {recruiter_notes(candidate)}",
                    "",
                    "**Score Breakdown**",
                    "",
                ]
            )
            for category, score in candidate["scores"].items():
                lines.append(f"- {category}: {score}/{SCORING_WEIGHTS[category]}")

            lines.extend(["", "**Strengths**", ""])
            lines.extend(format_list(candidate["strengths"]))
            lines.extend(["", "**Gaps / Follow-Up Questions**", ""])
            lines.extend(format_list(candidate["gaps"]))

            if candidate.get("notes"):
                lines.extend(["", f"**Note:** {candidate['notes']}"])
            lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


def write_outreach_messages(scored_candidates: list[dict], path: Path) -> None:
    lines = [
        "# AI Recruiting Shortlist Assistant - Outreach Messages",
        "",
        DISCLAIMER,
        "",
        "## Recruiter Review Notes",
        "",
        "These messages are draft starting points. Confirm candidate details, role fit, and company-specific language before sending.",
        "",
    ]

    if not scored_candidates:
        lines.append("No outreach messages generated because no resumes were found.")
    else:
        for candidate in scored_candidates:
            outreach = outreach_message_for(candidate)
            lines.extend(
                [
                    f"## {candidate['candidate_name']}",
                    "",
                    f"**Match Tier:** {candidate['recommendation']} | **Score:** {candidate['total_score']}/100",
                    "",
                    f"**Recruiter Notes:** {recruiter_notes(candidate)}",
                    "",
                    "**Draft Message:**",
                    "",
                    outreach,
                    "",
                ]
            )

    path.write_text("\n".join(lines), encoding="utf-8")


def format_list(items: list[str]) -> list[str]:
    if not items:
        return ["- None noted."]
    return [f"- {item}" for item in items]


def summary_line(scored_candidates: list[dict]) -> str:
    total = len(scored_candidates)
    strong = count_by_tier(scored_candidates, "Strong Match")
    possible = count_by_tier(scored_candidates, "Possible Match")
    weak = count_by_tier(scored_candidates, "Weak Match")
    return (
        f"Reviewed {total} candidate resume(s). "
        f"Results: {strong} Strong Match, {possible} Possible Match, and {weak} Weak Match."
    )


def markdown_summary_table(scored_candidates: list[dict]) -> list[str]:
    lines = [
        "| Rank | Candidate | Score | Match Tier | Submission Summary |",
        "| --- | --- | ---: | --- | --- |",
    ]
    for rank, candidate in enumerate(scored_candidates, start=1):
        lines.append(
            f"| {rank} | {candidate['candidate_name']} | {candidate['total_score']}/100 | "
            f"{candidate['recommendation']} | {submission_summary(candidate)} |"
        )
    return lines


def submission_summary(candidate: dict) -> str:
    score = candidate["total_score"]
    if score >= 80:
        return "Prioritize for recruiter screen and hiring-manager review."
    if score >= 60:
        return "Review after strongest matches; verify gaps before submission."
    return "Do not prioritize for this role based on the current resume."


def recruiter_notes(candidate: dict) -> str:
    strengths = candidate.get("strengths", [])
    gaps = candidate.get("gaps", [])
    top_strength = strengths[0] if strengths else "No clear differentiating strength captured."
    top_gap = gaps[0] if gaps else "No major gap captured."

    if candidate["total_score"] >= 80:
        return f"Strong alignment. Highlight: {top_strength}"
    if candidate["total_score"] >= 60:
        return f"Potential fit with follow-up needed. Confirm: {top_gap}"
    return f"Low alignment for this opening. Main concern: {top_gap}"


def outreach_message_for(candidate: dict) -> str:
    if candidate["total_score"] < 60:
        return "No outreach recommended for this role based on the current match score."
    return candidate["outreach_message"]


def count_by_tier(scored_candidates: list[dict], tier: str) -> int:
    return sum(1 for candidate in scored_candidates if candidate["recommendation"] == tier)
