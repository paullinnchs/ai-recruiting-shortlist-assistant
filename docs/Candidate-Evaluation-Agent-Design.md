# Candidate Evaluation Agent Design

## 1. Identity

**Agent Name:** Candidate Evaluation Agent

**Version:** 1.0

**Purpose:** Evaluate candidates against validated hiring criteria and produce evidence-based recommendations while identifying insufficient job requirements, missing candidate evidence, and situations requiring human review.

**Primary Responsibility:** Determine whether enough reliable information exists to evaluate a candidate fairly and, when it does, assess the candidate against the defined role requirements.

**Scope:** Candidate evaluation and recommendation. The agent does not make final hiring decisions.

---

## 2. Business Problem

Candidate evaluation is only as reliable as the hiring criteria being used.

Job descriptions are frequently incomplete, overly generic, outdated, or written without enough detail about required knowledge, skills, abilities, experience, education, certifications, or the characteristics of a strong candidate.

When poor job descriptions are used as the primary input for AI candidate matching or ranking, the system can produce precise-looking results based on weak criteria — effectively creating a garbage-in, garbage-out problem.

The Candidate Evaluation Agent addresses this by validating the quality of the hiring criteria before evaluating candidates.

If sufficient criteria exist, the agent proceeds with candidate evaluation.

If critical criteria are missing or ambiguous, the agent identifies the gaps and routes the requirement for human clarification before producing a definitive candidate recommendation.

---

## 3. Stakeholders

### Primary

* Recruiters
* Recruiting agency owners and leaders
* Talent Acquisition teams
* Hiring managers

### Secondary

* Recruiting Operations
* HR / People Operations
* Client-facing staffing teams
* Candidates
* Business leaders responsible for hiring outcomes

### Human Decision Owner

The recruiter and/or hiring manager retains responsibility for the final hiring decision.
## 4. What Does It Do?

The Candidate Evaluation Agent:

1. Reviews the job description and hiring criteria.
2. Determines whether the role requirements are specific enough to support reliable candidate evaluation.
3. Identifies missing or ambiguous criteria.
4. Stops and requests human clarification when critical hiring criteria are insufficient.
5. Builds a normalized candidate evaluation profile when the criteria are sufficient.
6. Reviews candidate evidence against the defined requirements.
7. Applies the existing scoring rubric where appropriate.
8. Identifies candidate strengths, gaps, and missing evidence.
9. Produces an evidence-based recommendation.
10. Assigns a confidence level to the recommendation.
11. Routes low-confidence or ambiguous cases for human review.
12. Produces structured outputs for recruiter use.

The agent does not make the final hiring decision.

---

## 5. Why Does It Matter?

Candidate matching and ranking quality depends heavily on the quality of the hiring criteria.

Poor or incomplete job descriptions can cause:

* Weak candidate matching
* False positives
* False negatives
* Inconsistent recruiter decisions
* Wasted sourcing and screening time
* Poor candidate pipelines
* Reduced trust in AI recruiting tools

The agent improves the process by validating the hiring criteria before candidate scoring begins.

This helps prevent automated systems from producing confident-looking recommendations based on incomplete or poor-quality inputs.

It also provides recruiters and hiring managers with a structured way to identify what information is missing before evaluating talent.

---

## 6. What Does Good Look Like?

A successful Candidate Evaluation Agent should:

* Refuse to produce a definitive candidate recommendation when critical hiring criteria are missing.
* Clearly identify which job requirements need clarification.
* Separate required qualifications from preferred qualifications.
* Evaluate candidates using evidence found in the resume rather than assumptions.
* Preserve the existing 100-point scoring framework where it remains useful.
* Explain the primary reasons behind each recommendation.
* Identify missing candidate evidence instead of treating missing information as confirmed absence.
* Assign a confidence level to candidate recommendations.
* Route low-confidence or ambiguous cases to a human recruiter.
* Produce consistent structured outputs across candidates.
* Continue operating if the primary LLM is unavailable by using the existing deterministic fallback where appropriate.
* Avoid inventing candidate qualifications or experience.

### Initial Success Criteria

For Version 1.0:

* 100% of candidate evaluations must pass through the job-criteria readiness check.
* No candidate receives a definitive recommendation when the agent determines the hiring criteria are insufficient.
* Every recommendation includes supporting evidence, identified gaps, and confidence.
* Low-confidence evaluations are explicitly flagged for human review.
* Existing deterministic scoring remains available as a fallback if the LLM scoring path fails.
* All agent decisions can be reviewed through logs or structured output.

## 7. Inputs

The Candidate Evaluation Agent requires two primary inputs.

### Role Requirements

Initial input may include:

* Job description
* Job title
* Required knowledge, skills, and abilities (KSAs)
* Minimum experience
* Required education
* Required certifications or licenses
* Required domain or industry experience
* Required tools or platforms
* Location requirements
* Work authorization requirements
* Availability requirements
* Preferred qualifications
* Description or example of an ideal candidate

Not every field must be present.

The agent determines whether enough critical information exists to proceed.

### Candidate Information

Initial candidate input may include:

* Resume
* Candidate name
* Employment history
* Skills
* Education
* Certifications
* Tools/platform experience
* Industry/domain experience
* Location
* Work authorization
* Availability

The agent must distinguish between:

**Confirmed evidence** — explicitly supported by candidate information.

**Missing evidence** — information not provided.

Missing evidence must not automatically be interpreted as failure to meet a requirement.

---

## 8. Decision Logic

The agent follows this decision sequence:

### Step 1 — Validate Hiring Criteria

Review the role requirements.

Determine:

**SUFFICIENT**

or

**INSUFFICIENT**

If insufficient:

1. Identify critical missing information.
2. Generate clarification questions.
3. Route to human review.
4. Stop candidate scoring until sufficient criteria exist.

### Step 2 — Build Evaluation Profile

If sufficient, convert the hiring requirements into structured criteria:

* Must-have
* Preferred
* Experience
* KSA
* Education/certification
* Domain
* Tools/platforms
* Logistics

### Step 3 — Evaluate Candidate Evidence

Compare candidate evidence against each relevant criterion.

Classify evidence as:

* Meets
* Partially meets
* Does not meet
* Unknown / insufficient evidence

### Step 4 — Score

Apply the defined scoring rubric to supported criteria.

Do not award points based on assumptions.

### Step 5 — Evaluate Confidence

Determine whether enough evidence exists to support the recommendation.

Possible confidence levels:

* High
* Medium
* Low

### Step 6 — Decide Next Action

The agent selects one of the following:

**RECOMMEND**

Evidence supports moving the candidate forward.

**REVIEW**

The candidate may be viable, but ambiguity or missing evidence requires recruiter review.

**DO NOT RECOMMEND**

Evidence shows meaningful misalignment with defined requirements.

**CLARIFICATION REQUIRED**

The role criteria themselves are insufficient to make reliable candidate evaluations.

The final hiring decision remains with a human.

---

## 9. Tools

Version 1.0 should remain intentionally simple.

### Required

**Resume Parser**

Extracts candidate information from supported resume formats.

**LLM**

Performs contextual evaluation, reasoning, evidence assessment, and structured recommendation generation.

**Deterministic Scoring Engine**

Provides rule-based scoring and an available fallback when appropriate.

**File Output**

Produces structured reports and candidate results.

### Existing Capabilities to Preserve

The current repository already provides:

* Resume parsing
* OpenAI-based evaluation
* Heuristic scoring fallback
* Candidate ranking
* Report generation
* Outreach generation
* Web interface

These capabilities should be reused where they remain appropriate rather than rebuilt unnecessarily.

---

## 10. Knowledge Sources

Version 1.0 should rely primarily on information explicitly supplied for the hiring requirement and candidate.

### Role Knowledge

* Job description
* Hiring-manager clarification
* Defined evaluation criteria
* Required vs preferred qualifications
* Ideal candidate profile when available

### Candidate Knowledge

* Resume
* Candidate-provided information
* Other explicitly approved candidate information

### Agent Knowledge

* Candidate Evaluation Skill
* Evaluation rubric
* JD readiness criteria
* Business rules
* Guardrails

### External Knowledge

Version 1.0 should not automatically search the internet or external candidate sources.

External enrichment can be considered later if there is a legitimate business requirement, appropriate permission, and clear value.

The first objective is to make the core evaluation agent reliable before adding additional tools or data sources.

## 11. Outputs

The Candidate Evaluation Agent should produce structured outputs that allow a recruiter to understand both the recommendation and the evidence supporting it.

### Job Criteria Readiness

Before candidate evaluation:

* Readiness status: Sufficient / Insufficient
* Missing critical criteria
* Ambiguous criteria
* Clarification questions
* Recommended next action

### Candidate Evaluation

For each candidate:

* Candidate name
* Total score
* Recommendation
* Confidence level
* Supporting evidence
* Strengths
* Gaps
* Missing or unknown evidence
* Required qualifications met
* Required qualifications not met
* Preferred qualifications met
* Human-review flag
* Recommended next action

### Existing Outputs

Where appropriate, preserve:

* `ranked_shortlist.csv`
* `candidate_report.md`
* `outreach_messages.md`

Outputs may be expanded to expose the agent's reasoning, confidence, and review status.

---

## 12. Guardrails

The agent must:

* Evaluate only against defined hiring criteria.
* Never invent candidate qualifications, experience, education, certifications, or skills.
* Never assume missing resume information means the candidate lacks the qualification.
* Distinguish missing evidence from confirmed misalignment.
* Clearly distinguish required qualifications from preferred qualifications.
* Stop candidate evaluation when critical hiring criteria are insufficient.
* Explain recommendations using evidence available in the approved inputs.
* Flag uncertainty rather than manufacture confidence.
* Route ambiguous or low-confidence cases for human review.
* Never make the final hiring decision.
* Never contact a candidate automatically in Version 1.0.
* Never reject a candidate automatically in Version 1.0.
* Never access external candidate information unless explicitly authorized in a future version.

---

## 13. Human-in-the-Loop

Human involvement is intentional in Version 1.0.

### Hiring Criteria

Human review is required when:

* Critical role requirements are missing.
* Required and preferred qualifications cannot be distinguished.
* Minimum experience is unclear.
* Required education or certifications are ambiguous.
* The ideal candidate profile cannot reasonably be inferred from the supplied information.

The agent should identify the gap and ask targeted clarification questions.

### Candidate Evaluation

Human review is required when:

* Recommendation confidence is low.
* Candidate evidence is materially incomplete.
* Conflicting evidence exists.
* A candidate appears close to a required threshold.
* The agent cannot reliably distinguish between a true qualification gap and missing information.
* An unusual situation falls outside the defined evaluation criteria.

### Decision Authority

The agent may:

* Analyze
* Score
* Rank
* Recommend
* Flag
* Request clarification
* Prepare recruiter outputs

The human recruiter or hiring manager retains authority to:

* Advance
* Reject
* Interview
* Contact
* Hire

---

## 14. Stop and Completion Conditions

The agent must have explicit conditions for continuing, stopping, escalating, and completing its work.

### Stop

Stop candidate evaluation when:

* Hiring criteria are insufficient.
* Required input cannot be parsed.
* A critical system failure prevents reliable evaluation.
* Continuing would require unsupported assumptions.

### Escalate

Escalate for human review when:

* Confidence is low.
* Important candidate evidence is unknown.
* Criteria are ambiguous.
* Conflicting information exists.
* The situation falls outside established rules.

### Continue

Continue when:

* Hiring criteria are sufficient.
* Candidate information can be evaluated.
* Required tools are functioning.
* The agent remains within its defined permissions and guardrails.

### Complete

The task is complete when:

1. Hiring criteria have been validated.
2. Each candidate has been evaluated against those criteria.
3. Evidence and gaps have been identified.
4. Confidence has been assigned.
5. Appropriate recommendation or human-review status has been assigned.
6. Required outputs have been generated.
7. The execution can be reviewed through structured results or logs.

The agent should not continue taking actions after the defined objective has been completed.

## 15. Candidate Evaluation Skill

The Candidate Evaluation Agent should use a reusable skill that defines how candidate evaluation is performed.

### Skill Name

Candidate Evaluation Skill

### Purpose

Provide a consistent, evidence-based method for evaluating candidates against validated hiring criteria.

### When to Use

Use when:

* Hiring criteria have been validated as sufficient.
* Candidate information is available for review.
* The agent needs to determine candidate fit, gaps, confidence, and next action.

### When Not to Use

Do not use when:

* Hiring criteria are insufficient.
* Candidate information cannot be parsed.
* Critical role requirements are unknown.
* The task requires a final hiring decision.
* The task requires unauthorized external candidate research.

### Required Inputs

* Validated hiring criteria
* Candidate resume or approved candidate information
* Scoring rubric
* Required vs preferred qualifications

### Procedure

1. Review the validated hiring criteria.
2. Identify must-have requirements.
3. Identify preferred requirements.
4. Review the candidate evidence.
5. Match evidence to each requirement.
6. Distinguish confirmed evidence from missing evidence.
7. Identify clear strengths.
8. Identify confirmed gaps.
9. Identify unknown or insufficient evidence.
10. Apply the scoring rubric.
11. Determine recommendation.
12. Determine confidence.
13. Determine whether human review is required.
14. Generate structured output.

### Output

The skill returns:

* Score
* Recommendation
* Confidence
* Supporting evidence
* Strengths
* Gaps
* Unknown evidence
* Human-review flag
* Recommended next action

### Guardrails

The skill must:

* Use only available evidence.
* Never invent qualifications.
* Never treat missing evidence as confirmed absence.
* Never make the final hiring decision.
* Flag uncertainty.
* Escalate when the evidence is insufficient.

---

## 16. Evaluation and Test Plan

Version 1.0 should be tested for both technical performance and recruiting usefulness.

### Test Category 1 — Strong Job Description

Input:

A clear job description containing:

* Required skills
* Minimum experience
* Required qualifications
* Preferred qualifications
* Role responsibilities
* Relevant domain context

Expected:

* Job criteria readiness = Sufficient
* Candidate evaluation proceeds

---

### Test Category 2 — Weak Job Description

Input:

A generic or incomplete job description.

Expected:

* Job criteria readiness = Insufficient
* Missing criteria are identified
* Clarification questions are produced
* Candidate scoring does not proceed

---

### Test Category 3 — Strong Candidate Match

Input:

Candidate clearly demonstrates the required qualifications.

Expected:

* Strong score
* Supporting evidence identified
* High or appropriate confidence
* Recommendation supported by evidence

---

### Test Category 4 — Weak Candidate Match

Input:

Candidate clearly lacks important defined requirements.

Expected:

* Confirmed gaps identified
* Lower score
* Recommendation reflects evidence
* No invented qualifications

---

### Test Category 5 — Missing Candidate Evidence

Input:

Candidate resume does not mention an important qualification.

Expected:

The agent classifies it as:

Unknown / insufficient evidence

rather than automatically:

Does not meet

when absence cannot be confirmed.

---

### Test Category 6 — Ambiguous Candidate

Input:

Candidate appears close to requirements but evidence is incomplete or conflicting.

Expected:

* Confidence reduced
* Human-review flag enabled
* Clear explanation of ambiguity

---

### Test Category 7 — LLM Failure

Simulate unavailable or failed LLM execution.

Expected:

* Existing deterministic fallback executes where appropriate
* Failure is logged
* Output clearly identifies that fallback scoring was used

---

### Test Category 8 — Hallucination Check

Candidate does not contain a specific skill, certification, employer, or experience.

Expected:

The agent must not claim that the candidate has it.

---

### Version 1.0 Evaluation Questions

For every test run ask:

1. Did the JD readiness gate behave correctly?
2. Did the agent use only available evidence?
3. Did it distinguish missing evidence from confirmed gaps?
4. Was the recommendation supported by the evidence?
5. Was confidence reasonable?
6. Was human review triggered when appropriate?
7. Did fallback behavior work?
8. Were outputs understandable to a recruiter?
9. Can we reconstruct what happened?
10. Did the system avoid unsupported assumptions?

---

## 17. Version 1.0 Architecture

Version 1.0 should remain intentionally simple.

### Architecture

JOB DESCRIPTION

↓

JD READINESS CHECK

↓

Sufficient?

### NO

Identify missing criteria

↓

Generate clarification questions

↓

Human Review

↓

STOP

### YES

Build normalized hiring criteria

↓

For each candidate:

Candidate Resume

↓

Candidate Evaluation Skill

↓

Evidence Assessment

↓

Existing Scoring Rubric

↓

Recommendation + Confidence

↓

Confidence sufficient?

### NO

Human Review

### YES

Structured Recommendation

↓

Generate Outputs

↓

Complete

---

### Core Components

Version 1.0 should contain:

* One Candidate Evaluation Agent
* One Candidate Evaluation Skill
* JD Readiness Check
* Existing 100-point scoring framework
* Existing OpenAI evaluation capability
* Existing deterministic heuristic fallback
* Confidence handling
* Human-review routing
* Guardrails
* Structured outputs
* Basic logging
* Evaluation tests

### Version 1.0 Should Not Include

To keep the first agent focused, do not add:

* Multiple agents
* Supervisor agent
* Internet candidate research
* Automated candidate rejection
* Automated candidate communication
* Autonomous sourcing
* Complex long-term memory
* Unnecessary external integrations

These may be evaluated in future versions after the core agent performs reliably.

---

# Version 1.0 Objective

Build one focused Candidate Evaluation Agent that reliably determines whether enough information exists to evaluate talent, evaluates candidates using available evidence, handles uncertainty appropriately, and produces recruiter-ready recommendations without pretending to know more than the available data supports.
