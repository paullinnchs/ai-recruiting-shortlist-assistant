from generate_outputs import write_outputs
from parse_resumes import read_job_description, read_resumes
from score_candidates import score_all_candidates


def main() -> None:
    print("AI Recruiting Shortlist Assistant")
    print("Reading job description and resumes...")

    job_description = read_job_description()
    resumes = read_resumes()

    if not resumes:
        print("No supported resumes found in input/resumes/. Add .txt, .pdf, or .docx files.")
        write_outputs([])
        return

    print(f"Scoring {len(resumes)} resume(s)...")
    scored_candidates = score_all_candidates(job_description, resumes)

    print("Writing outputs...")
    write_outputs(scored_candidates)

    print("Done.")
    print("- output/ranked_shortlist.csv")
    print("- output/candidate_report.md")
    print("- output/outreach_messages.md")


if __name__ == "__main__":
    main()
