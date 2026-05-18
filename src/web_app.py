from html import escape
from pathlib import Path
from tempfile import TemporaryDirectory

from flask import Flask, request
from werkzeug.utils import secure_filename

from parse_resumes import SUPPORTED_RESUME_EXTENSIONS, extract_resume_text, guess_candidate_name
from score_candidates import SCORING_WEIGHTS, score_all_candidates


app = Flask(__name__)


PAGE_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>AI Recruiting Shortlist Assistant Web Demo</title>
  <style>
    :root {{
      --bg: #f5f7fa;
      --surface: #ffffff;
      --text: #1f2933;
      --muted: #617080;
      --line: #d8dee8;
      --accent: #0f766e;
      --accent-dark: #115e59;
      --soft: #e8f3f1;
      --warning: #946200;
    }}

    * {{
      box-sizing: border-box;
    }}

    body {{
      margin: 0;
      font-family: Arial, Helvetica, sans-serif;
      color: var(--text);
      background: var(--bg);
      line-height: 1.55;
    }}

    header {{
      background: var(--surface);
      border-bottom: 1px solid var(--line);
    }}

    .topbar {{
      max-width: 1180px;
      margin: 0 auto;
      padding: 18px 24px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 18px;
    }}

    .brand {{
      font-weight: 700;
      color: var(--accent-dark);
    }}

    .topbar a {{
      color: var(--muted);
      text-decoration: none;
      font-size: 14px;
    }}

    main {{
      max-width: 1180px;
      margin: 0 auto;
      padding: 42px 24px 64px;
    }}

    .intro {{
      max-width: 820px;
      margin-bottom: 28px;
    }}

    h1 {{
      margin: 0 0 12px;
      font-size: 40px;
      line-height: 1.1;
      letter-spacing: 0;
    }}

    .intro p {{
      margin: 0;
      color: var(--muted);
      font-size: 17px;
    }}

    .layout {{
      display: grid;
      grid-template-columns: minmax(320px, 0.9fr) minmax(0, 1.1fr);
      gap: 24px;
      align-items: start;
    }}

    .panel {{
      background: var(--surface);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 22px;
      box-shadow: 0 12px 30px rgba(31, 41, 51, 0.06);
    }}

    label {{
      display: block;
      margin-bottom: 8px;
      font-weight: 700;
      font-size: 14px;
    }}

    textarea,
    input[type="file"] {{
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #fbfcfd;
      color: var(--text);
      font: inherit;
    }}

    textarea {{
      min-height: 260px;
      resize: vertical;
      padding: 12px;
    }}

    input[type="file"] {{
      padding: 12px;
    }}

    .field {{
      margin-bottom: 18px;
    }}

    button,
    .button {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-height: 42px;
      padding: 0 18px;
      border: 0;
      border-radius: 6px;
      background: var(--accent);
      color: #ffffff;
      font-weight: 700;
      text-decoration: none;
      cursor: pointer;
    }}

    .helper {{
      margin: 8px 0 0;
      color: var(--muted);
      font-size: 13px;
    }}

    .notice {{
      margin-bottom: 16px;
      padding: 12px 14px;
      border-radius: 6px;
      background: #fff7df;
      color: var(--warning);
      font-size: 14px;
    }}

    .empty {{
      color: var(--muted);
      background: var(--soft);
      border: 1px solid #c9dfdb;
      border-radius: 8px;
      padding: 18px;
    }}

    .results {{
      display: grid;
      gap: 14px;
    }}

    .candidate {{
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 18px;
      background: #fbfcfd;
    }}

    .candidate-head {{
      display: flex;
      justify-content: space-between;
      gap: 18px;
      align-items: flex-start;
      margin-bottom: 12px;
    }}

    .candidate h3 {{
      margin: 0;
      font-size: 20px;
    }}

    .score {{
      color: var(--accent-dark);
      font-weight: 700;
      white-space: nowrap;
    }}

    .tier {{
      display: inline-block;
      margin-top: 6px;
      padding: 3px 8px;
      border-radius: 999px;
      background: var(--soft);
      color: var(--accent-dark);
      font-size: 13px;
      font-weight: 700;
    }}

    table {{
      width: 100%;
      border-collapse: collapse;
      margin: 12px 0;
      font-size: 14px;
    }}

    th,
    td {{
      padding: 8px 0;
      border-bottom: 1px solid var(--line);
      text-align: left;
      vertical-align: top;
    }}

    th:last-child,
    td:last-child {{
      text-align: right;
      white-space: nowrap;
    }}

    .list-title {{
      margin: 12px 0 4px;
      font-weight: 700;
    }}

    ul {{
      margin: 0;
      padding-left: 20px;
      color: var(--muted);
    }}

    footer {{
      max-width: 1180px;
      margin: 0 auto;
      padding: 24px;
      color: var(--muted);
      font-size: 13px;
    }}

    @media (max-width: 880px) {{
      .layout {{
        grid-template-columns: 1fr;
      }}

      h1 {{
        font-size: 32px;
      }}
    }}
  </style>
</head>
<body>
  <header>
    <div class="topbar">
      <div class="brand">AI Recruiting Shortlist Assistant</div>
      <a href="/">Web Demo</a>
    </div>
  </header>

  <main>
    <section class="intro">
      <h1>Web Demo</h1>
      <p>Paste a job description, upload multiple `.txt`, `.pdf`, or `.docx` resumes, and review ranked candidate results directly on the page.</p>
    </section>

    <div class="layout">
      <form class="panel" method="post" enctype="multipart/form-data">
        <div class="field">
          <label for="job_description">Job Description</label>
          <textarea id="job_description" name="job_description" required>{job_description}</textarea>
        </div>

        <div class="field">
          <label for="resumes">Resume Files</label>
          <input id="resumes" name="resumes" type="file" accept=".txt,.pdf,.docx" multiple required>
          <p class="helper">This web demo supports multiple .txt, .pdf, and .docx resume uploads. API keys stay on the server and are never sent to the browser.</p>
        </div>

        <button type="submit">Analyze Candidates</button>
      </form>

      <section class="panel">
        <h2>Ranked Results</h2>
        {messages}
        {results}
      </section>
    </div>
  </main>

  <footer>
    Recruiter-assist disclaimer: review all generated content for accuracy, bias, legal compliance, and job-relatedness before use.
  </footer>
</body>
</html>
"""


def index():
    results_html = '<div class="empty">Upload resumes and click Analyze Candidates to see ranked results.</div>'
    messages_html = ""
    job_description = ""

    if request.method == "POST":
        job_description = request.form.get("job_description", "").strip()
        resumes, skipped_files = read_uploaded_resumes(request.files.getlist("resumes"))

        if not job_description:
            messages_html = '<div class="notice">Please paste a job description before analyzing candidates.</div>'
        elif not resumes:
            messages_html = '<div class="notice">Please upload at least one non-empty `.txt`, `.pdf`, or `.docx` resume.</div>'
        else:
            scored_candidates = score_all_candidates(job_description, resumes)
            results_html = render_results(scored_candidates)

        if skipped_files:
            skipped = ", ".join(escape(name) for name in skipped_files)
            messages_html += f'<div class="notice">Skipped unsupported or empty file(s): {skipped}</div>'

    return PAGE_TEMPLATE.format(
        job_description=escape(job_description),
        messages=messages_html,
        results=results_html,
    )


app.add_url_rule("/", "index", index, methods=["GET", "POST"])


def read_uploaded_resumes(files) -> tuple[list[dict], list[str]]:
    resumes = []
    skipped_files = []

    with TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        for uploaded_file in files:
            file_name = secure_filename(uploaded_file.filename or "")
            extension = Path(file_name).suffix.lower()

            if not file_name or extension not in SUPPORTED_RESUME_EXTENSIONS:
                skipped_files.append(uploaded_file.filename or "unnamed file")
                continue

            resume_path = temp_path / file_name
            uploaded_file.save(resume_path)

            try:
                resume_text = extract_resume_text(resume_path).strip()
            except Exception:
                skipped_files.append(file_name)
                continue

            if not resume_text:
                skipped_files.append(file_name)
                continue

            resumes.append(
                {
                    "file_name": file_name,
                    "candidate_name": guess_candidate_name(resume_text, resume_path.stem),
                    "text": resume_text,
                }
            )

    return resumes, skipped_files


def render_results(scored_candidates: list[dict]) -> str:
    cards = []
    for rank, candidate in enumerate(scored_candidates, start=1):
        score_rows = []
        for category, max_points in SCORING_WEIGHTS.items():
            score = candidate["scores"].get(category, 0)
            score_rows.append(
                f"<tr><td>{escape(category)}</td><td>{score}/{max_points}</td></tr>"
            )

        strengths = "".join(f"<li>{escape(item)}</li>" for item in candidate.get("strengths", []))
        gaps = "".join(f"<li>{escape(item)}</li>" for item in candidate.get("gaps", []))

        cards.append(
            f"""
            <article class="candidate">
              <div class="candidate-head">
                <div>
                  <h3>{rank}. {escape(candidate["candidate_name"])}</h3>
                  <span class="tier">{escape(candidate["recommendation"])}</span>
                </div>
                <div class="score">{candidate["total_score"]}/100</div>
              </div>
              <table>
                <tbody>
                  {''.join(score_rows)}
                </tbody>
              </table>
              <div class="list-title">Strengths</div>
              <ul>{strengths or "<li>No strengths captured.</li>"}</ul>
              <div class="list-title">Gaps / Follow-Up</div>
              <ul>{gaps or "<li>No major gaps captured.</li>"}</ul>
            </article>
            """
        )

    return f'<div class="results">{"".join(cards)}</div>'


if __name__ == "__main__":
    app.run(debug=True, use_reloader=False)
