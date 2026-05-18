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
        "rank",
        "candidate_name",
        "file_name",
        "total_score",
        "recommendation",
        *SCORING_WEIGHTS.keys(),
    ]

    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        for rank, candidate in enumerate(scored_candidates, start=1):
            row = {
                "rank": rank,
                "candidate_name": candidate["candidate_name"],
                "file_name": candidate["file_name"],
                "total_score": candidate["total_score"],
                "recommendation": candidate["recommendation"],
            }
            row.update(candidate["scores"])
            writer.writerow(row)


def write_candidate_report(scored_candidates: list[dict], path: Path) -> None:
    lines = [
        "# Candidate Report",
        "",
        DISCLAIMER,
        "",
    ]

    if not scored_candidates:
        lines.append("No resumes were found in `input/resumes/`.")
    else:
        for rank, candidate in enumerate(scored_candidates, start=1):
            lines.extend(
                [
                    f"## {rank}. {candidate['candidate_name']} - {candidate['total_score']}/100",
                    "",
                    f"**Recommendation:** {candidate['recommendation']}",
                    "",
                    "### Score Breakdown",
                    "",
                ]
            )
            for category, score in candidate["scores"].items():
                lines.append(f"- {category}: {score}/{SCORING_WEIGHTS[category]}")

            lines.extend(["", "### Strengths", ""])
            lines.extend(format_list(candidate["strengths"]))
            lines.extend(["", "### Gaps", ""])
            lines.extend(format_list(candidate["gaps"]))

            if candidate.get("notes"):
                lines.extend(["", f"**Note:** {candidate['notes']}"])
            lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


def write_outreach_messages(scored_candidates: list[dict], path: Path) -> None:
    lines = [
        "# Outreach Messages",
        "",
        DISCLAIMER,
        "",
    ]

    if not scored_candidates:
        lines.append("No outreach messages generated because no resumes were found.")
    else:
        for candidate in scored_candidates:
            lines.extend(
                [
                    f"## {candidate['candidate_name']}",
                    "",
                    candidate["outreach_message"],
                    "",
                ]
            )

    path.write_text("\n".join(lines), encoding="utf-8")


def format_list(items: list[str]) -> list[str]:
    if not items:
        return ["- None noted."]
    return [f"- {item}" for item in items]
