import run_log as run_log_module
from generate_outputs import write_outputs
from jd_readiness import check_readiness, format_readiness_report
from parse_resumes import read_job_description, read_resumes
from score_candidates import score_all_candidates


def main() -> None:
    print("AI Recruiting Shortlist Assistant")
    print("Reading job description and resumes...")

    log = run_log_module.start_run()
    job_description = read_job_description()

    print("Checking whether the job description supports a reliable evaluation...")
    readiness = check_readiness(job_description, run_log=log)

    if not readiness.is_sufficient:
        print()
        print(format_readiness_report(readiness))
        print()
        print("Candidate evaluation did not run, so no candidate outputs were written.")
        print("Any files already in output/ are from an earlier run.")
        log.complete(status="stopped", stop_reason="jd_criteria_insufficient")
        return

    resumes = read_resumes()

    if not resumes:
        print("No supported resumes found in input/resumes/. Add .txt, .pdf, or .docx files.")
        write_outputs([])
        log.complete(status="completed", candidates=0)
        return

    print(f"Scoring {len(resumes)} resume(s)...")
    scored_candidates = score_all_candidates(job_description, resumes, run_log=log)

    print("Writing outputs...")
    write_outputs(scored_candidates)

    print("Done.")
    print("- output/ranked_shortlist.csv")
    print("- output/candidate_report.md")
    print("- output/outreach_messages.md")
    log.complete(status="completed", candidates=len(scored_candidates))


if __name__ == "__main__":
    main()
