# Project plan: course requirements, grading, report, timeline, risks

> Read this file (rule "Read-when" in `CLAUDE.md`) before working on the proposal, the report, the slides, grading questions, roles, the timeline, risks or extensions. Technical rules, decisions, the pipeline and the current to-do list are in `CLAUDE.md`; data and method decisions with evidence are in `docs/decision_log.md`.

Last updated: 9 Nov 2026 · PDS Group 18

**Status of decisions (9 Nov 2026):** all decisions and the plan so far (D1–D16, timeline, roles) were prepared by one member and are **proposals** until the whole group has discussed and confirmed them. From now on, decisions are made by the group together.

## 1. Assignment brief: key facts

Full text: `../Informations/Assignment_brief_Final_Project.md` (copied from the course room on 6 Nov 2026; kept outside the repository). The chair's report template is still to be downloaded into `../Informations/`.

To pass, we need a baseline plus at least one more approach, implemented with sufficient care; everything else raises the grade.

| What | When |
| --- | --- |
| Group registration (3 members) via "Capstone Project Groups" | 15 Nov 2026, 23:59 (no group = no participation) |
| Topic proposal, max. 2 pages, via "Topic Proposal" | 30 Nov 2026, 23:59 |
| Supervisor feedback; no feedback means accepted | by 7 Dec 2026 |
| Final PDF report and all documentation | 18 Jan 2027, 23:59 |
| Presentation (10 min per group) | 25 Jan 2027, 15:00 (room to be announced) |

**Proposal must contain:** group members (name, matriculation number), working title and problem statement, dataset (source, size, license), target variable and evaluation metric, planned baseline and modelling approaches. Use the cleaned numbers from `02_clean.py` (≈230,000 non-cancelled departures, ≈23% delayed), not the raw row count.

**Required subgoals:** problem definition and motivation; EDA; clean, reproducible data pipeline; simple interpretable baseline; at least one more advanced approach; evaluation on a held-out test set with suitable metrics and error analysis.

**Optional extensions in the brief:** domain feature engineering or extra data sources; explainability (SHAP, LIME); prototype app or dashboard; systematic hyperparameter optimisation or robustness analysis.

**Report format:** scientific paper structure using the chair's template, 15–20 pages of main text (excluding title page, tables of contents, references, appendix), consistent citations, one final PDF that may link to notebooks or a documented GitHub repository. Mandatory sections: **Use of generative AI** (which parts, which prompts) and **Contributions** (role of each member).

**Grading criteria (brief):** clarity and relevance of the problem; data preparation and EDA; variety and appropriateness of models; originality; methodological rigour (splits, leakage, metrics) and performance against the baseline; documentation of failures, improvements and next steps; code and report documentation and template adherence; presentation quality; dashboard functionality if implemented.

## 2. How the course grades the project

**Graded deliverables:** the two-page proposal (gate: accepted unless feedback by 7 Dec), one final PDF report in the chair's template, the code (GitHub repository and/or notebooks linked from the PDF), the 10-minute presentation on 25 Jan 2027, and the dashboard (graded if implemented). Weights are not published; we treat the criteria as equal.

| Grading criterion | Evidence we provide | Where |
| --- | --- | --- |
| Clarity and relevance of the problem | One-sentence goal, DB 6-min threshold, two scenarios, passenger use case | Introduction |
| Data preparation and EDA | Data check table, cleaning rules with counts, coverage check, EDA figures (by service, hour, month, propagation) | Data |
| Variety and appropriateness of approaches | Rule-based baseline, logistic regression, LightGBM with justification; scenario A vs. A′ vs. B | Methodology, Results |
| Originality | Propagation features, scenario comparison with control model, weather and school holidays, connection check | Methodology, Discussion |
| Methodological rigour and performance vs. baseline | Chronological split, leakage rules and automated safeguards, PR-AUC, paired day-block bootstrap, test set used once | Methodology, Results |
| Failures, improvements, next steps | Error slices, top errors, limitations, next steps | Discussion |
| Documentation of code and report | README, docstrings, one-command pipeline, tests, template adherence, citations | Repository, whole report |
| Presentation | 10-minute talk, live demo plus recorded backup | Slides |
| Dashboard functionality | Deployed Streamlit app (test-period replay) with SHAP explanation | Results, appendix link |
| GenAI use and contributions (mandatory sections) | Members' AI-use logs merged into a table; role table | Dedicated sections |

**Success criteria.**

- **Pass:** B1, B2 and M-A trained and evaluated correctly on the chronological split, with a documented results table.
- **Good grade:** M-A beats B2 on PR-AUC; M-B clearly beats M-A′ (same training window); error analysis and SHAP documented; dashboard deployed.
- **Red flag:** scenario A ROC-AUC above ~0.95, a failed leakage test, or any model far above the others without a clear reason → stop and run the leakage safeguards.

## 3. Why LightGBM (for proposal, report and presentation)

1. **The data is tabular** (one row per departure, a few dozen columns). Gradient-boosted trees are the standard and usually strongest choice for tabular data; they generally match or beat deep learning on such data at a fraction of the effort (Grinsztajn et al., 2022).
2. **Interactions without manual work:** delay risk depends on combinations (ICE × Friday evening × rain). Logistic regression only sees them if built by hand; trees learn them.
3. **Missing values and categories handled natively:** earlier-stop features are missing for trains that start at Würzburg; line and destination are categorical.
4. **Fast:** seconds per fit on ~230,000 rows on a laptop, so tuning and repeated runs are cheap.
5. **Explainable:** SHAP's TreeExplainer gives exact explanations for tree models, needed for the report and the dashboard.

Not taken on faith: settings are chosen on validation only; all models are scored once on the same test rows; LightGBM is called better only if the 95% interval of its PR-AUC difference to B2 (paired day-block bootstrap) lies above zero (D13). Alternatives considered: XGBoost/CatBoost (same family, no clear advantage), Random Forest (usually slightly weaker; optional check), neural networks and sequence models (more effort, harder to explain, no expected gain).

## 4. Dashboard and other extensions

The minimum version (baselines, LightGBM, evaluation) comes first; extensions start only after it runs end to end.

**Streamlit dashboard** (committed; levels 1 and 2 committed, level 3 only if time allows):

| Level | What | Effort | Status |
| --- | --- | --- | --- |
| 1 | Replay of real test-period departures (Jul – Oct 2026, D15): choose a date and a departure → delay probability (scenario A) and actual outcome, previous-stop delay slider (scenario B), SHAP explanation | 1–2 days | Committed |
| 2 | Deploy on Streamlit Community Cloud with a public link | ~half a day | Committed |
| 3 | Connection check: probability of catching a transfer at Würzburg (e.g. ICE to RE with 7 min) | ~1 day | If time allows |

The app loads a saved model and a small table of test-period feature rows, never the raw data. No free future dates (weather and history would need live API calls). Not planned: FastAPI, a separate frontend, user accounts or live API calls.

| Extension | What we do | Criterion | Priority |
| --- | --- | --- | --- |
| Scenario A vs. A′ vs. B | Same model with and without earlier-stop delays, plus control model | Originality, discussion | Core |
| Weather and holiday features | Hourly weather; Bavarian and neighbouring school holidays | Feature engineering | Core |
| SHAP | Global importance plus per-prediction explanations (reused in the dashboard) | Explainability | Core |
| Error analysis | Largest errors by service, hour, weather, day type, horizon; typical failure cases | Failure documentation | Core |
| Calibration and robustness | Reliability diagram; performance by season (validation) and weather extremes | Rigour | If time allows |
| Random Forest check | Same features as M-A; confirms the LightGBM choice | Variety of models | If time allows |
| Regression or three-class variant | Delay minutes (MAE), or 0–5 / 6–15 / 16+ min | Variety of models | If time allows |
| Rolling-origin evaluation | Several chronological folds | Robustness | If time allows |

## 5. Timeline

Proposed timeline (to be agreed by the group): all code finished and frozen by 1 December, the whole project (report and slides) by **15 December**; the rest is buffer until the submission on 18 January.

| Phase / milestone | Dates |
| --- | --- |
| Setup and data pipeline, coverage check | 4 – 10 Nov 2026 |
| EDA, baselines, proposal draft | 11 – 17 Nov |
| ◆ Group registration (hard deadline) | 15 Nov |
| LightGBM A, A′ and B, evaluation | 18 – 24 Nov |
| ◆ Proposal submitted (official deadline 30 Nov) | ~20 Nov |
| SHAP, error analysis, dashboard | 25 Nov – 1 Dec |
| ◆ **Results frozen** | 1 Dec |
| ◆ Proposal feedback due | 7 Dec |
| Report writing | 2 – 10 Dec |
| Slides, final PDF | 11 – 15 Dec |
| ◆ **Everything finished** | 15 Dec |
| Buffer | 16 Dec 2026 – 17 Jan 2027 |
| ◆ Report and documentation submitted (hard deadline) | 18 Jan 2027, 23:59 |
| ◆ Presentation, 10 min | 25 Jan 2027, 15:00 |

The proposal goes in around 20 November, so any feedback (due by 7 December) arrives while modelling is still open. The proposal does not depend on results: draft it early in week 2.

## 6. To-do archive (all weeks)

The current and next week are mirrored in `CLAUDE.md`; this is the full list. Each week ends with a working result.

**Week 1 — setup and data (until 10 Nov 2026)**

- [x] Third member found (9 Nov 2026)
- [ ] **Register the group in the course room by 15 Nov 2026, 23:59** (hard deadline; not done on 10 Nov)
- [x] Assignment brief added and checked: submission 18 Jan 2027, presentation 25 Jan 2027 corrected
- [ ] Download the chair's report template into `../Informations/`
- [x] Repository scaffold: folders, `README.md`, `requirements.txt`, `.gitignore`, `pytest.ini`, `src/config.py`, `run_pipeline.py`
- [ ] Push the repository to GitHub and add the team as collaborators
- [x] `01_download.py` and `src/sql/01_filter_month.sql`; tested on Oct 2026 with `--show-example` (12,975 Würzburg rows, 82,842 earlier-stop rows, RB53 with 14 earlier stops)
- [x] All 28 months downloaded and filtered (`data/interim` 88 MB); `reports/checks/` reviewed: no missing months; ARV from Dec 2025; line format change Dec 2025
- [x] `checks/category_check.py`: ARV = relabel of RE8/RB8/RE80; NaN types and buses explained; category rules fixed
- [x] `src/features_config.py` and `tests/test_leakage.py`
- [x] Coverage check (`checks/coverage_check.py`, 5 sample months; output regenerated in the repository on 7 Nov): scenario B trains from 3 Nov 2025
- [x] `checks/data_quality_check.py` sections 1–4: 0 duplicate ids; change time never empty; 2 low-count days; full coverage from 3 Nov 2025; 11 "too punctual" days, all holidays/Sundays → no days excluded
- [x] `docs/decision_log.md` D1–D12 (7 Nov)
- [x] Plan review (7 Nov): D13 evaluation protocol, D14 baseline and history definitions, D15 dashboard replay, D16 disruption flags forbidden; CLAUDE.md split into CLAUDE.md + this file
- [ ] Share `docs/project_plan.md`, `docs/decision_log.md` and `CLAUDE.md` with both members and get agreement (incl. D13–D16)
- [ ] Write the cleaning step and save `wuerzburg_clean.parquet`

**Week 2 — EDA, baselines, proposal (until 17 Nov 2026)**

- [ ] Register the group by 15 Nov 2026 (hard deadline)
- [ ] EDA notebook: delay distribution; by service, line, hour, weekday, month; cancellations; exactly-on-time trend; propagation example; coverage figure; B horizon
- [ ] Weather and holiday join (`03_enrich.py`)
- [ ] `src/evaluate.py` + baselines B0, B1 (service × hour), B2 (logistic regression) on validation
- [ ] Draft the two-page proposal
- [ ] Write the Data section draft while the EDA is fresh

**Week 3 — main model (until 24 Nov 2026)**

- [ ] Submit the proposal around 20 Nov 2026 (official deadline 30 Nov)
- [ ] Scenario A and B feature tables (`04_features`); time-travel, earlier-stop and same-rows tests
- [ ] LightGBM for A, A′ and B; time-boxed tuning on validation; refit on train + validation
- [ ] Sanity checks: single-feature AUC, shuffled target
- [ ] Results table: baselines vs. LightGBM, A vs. A′ vs. B (PR-AUC, ROC-AUC, F1, Brier)
- [ ] Write the Methodology section draft

**Week 4 — extensions and dashboard (until 1 Dec 2026)**

- [ ] SHAP global and per prediction
- [ ] Error analysis and failure cases
- [ ] Streamlit app level 1, then deploy (level 2)
- [ ] Final run on the test set, once
- [ ] **Freeze results and figures**; no new features after this point

**Weeks 5–6 — report (until 10 Dec 2026)**

- [ ] Results, Discussion, Introduction, Related work, Conclusion in the chair's template
- [ ] Use of generative AI and Contributions sections from the members' AI-use logs
- [ ] Clean the repository: README with setup and run instructions, docstrings
- [ ] Cross-review: each member reads one other member's sections

**Week 7 — slides and finish (until 15 Dec 2026)**

- [ ] 10-minute presentation with a live dashboard demo and a recorded backup
- [ ] Final PDF export and check against the template
- [ ] Submit as soon as the submission is open

**16 Dec – 17 Jan:** buffer only. Submit by 18 Jan 2027, 23:59; rehearse once before 25 Jan 2027.

## 7. Roles and report structure

Proposed split (to be agreed by the group): each member owns one workstream end to end and reviews one other member's work. Names are assigned in the report's Contributions section, not here.

| Member | Owns | Report sections |
| --- | --- | --- |
| Member 1 | DuckDB/SQL pipeline, cleaning, coverage check, EDA, weather and holiday joins, Streamlit dashboard and deployment | Data, dashboard |
| Member 2 | Baselines, LightGBM, tuning, evaluation, leakage tests, error analysis | Methodology, Results |
| Member 3 | SHAP, related work, slides, report assembly in the template | Related work, explainability |
| All | Proposal, introduction, discussion, conclusion, cross-review | Introduction, Discussion, Conclusion |

| Section | Pages |
| --- | --- |
| 1. Introduction: problem, motivation, research questions | 1.5–2 |
| 2. Related work: train delay prediction | 2–3 |
| 3. Data: source, license, data check, coverage, EDA | 3–4 |
| 4. Methodology: pipeline, features, split, models, leakage rules and safeguards | 3–4 |
| 5. Results: models vs. baselines, scenario A vs. A′ vs. B, SHAP, dashboard | 2–3 |
| 6. Discussion: error analysis, limitations, next steps | 2–3 |
| 7. Conclusion | 0.5–1 |
| Use of generative AI; Contributions (both mandatory) | Check the template |

Code lives in one documented GitHub repository linked from the PDF. The decision log (`docs/decision_log.md`) is the source for the Data and Methodology sections.

## 8. Risks and mitigations

| Risk | Likelihood | Impact | Mitigation |
| --- | --- | --- | --- |
| Supervisor requests changes to the proposal | Low | Medium | Submit early (~20 Nov); data and EDA stay reusable; no feedback by 7 Dec = accepted |
| Group not registered by 15 Nov | Low | High | Third member found (9 Nov); register as soon as all three have joined |
| Monthly files large (download time, disk) | Low | Low | ~5 GB in total; raw files gitignored; `--delete-raw` if disk gets tight |
| Categories change over time (line format, ARV relabel) | Confirmed | Medium | `line_id` and `service` instead of raw `train_type`; RE/RB label check via `train_number` in cleaning; error analysis by lines 8 and 80 |
| Collection gaps / target is last reported time | Confirmed (changelog) | Medium | Day-level check done, no days excluded (D11); re-check if errors cluster in time blocks; named as limitation |
| Earlier stops missing before Nov 2025 | Confirmed | Medium | Scenario B trains from 3 Nov 2025; coverage table in the Data section |
| Joining earlier stops goes wrong (ride ID per schedule, midnight trips) | Medium | Medium | Ride ID + 12-hour window, linked via `wuerzburg_id`; validate on the RB53 example; earlier-stop timing test |
| A-vs-B difference confounded by training period | Confirmed | Medium | Control model M-A′ (D13) |
| Data leakage | Medium | High | Leakage rules, feature whitelist, forbidden columns, automated tests, sanity checks, second-member review |
| Scenario A scores modestly | High | Low | Expected; reported as a finding; scenario B carries performance |
| Dashboard grows beyond scope | Medium | Medium | Fixed three levels; replay only; level 3 only after the report draft exists |
| Report left to the end | Medium | High | Write each section in the week its work is done |
| Fallback needed | Low | High | German electricity demand (OPSD/SMARD), same pipeline pattern |

## 9. GenAI documentation

The brief requires a dedicated section stating which parts of the work used GenAI and which prompts were used.

- Each member keeps their own AI-use log (gitignored `genai_log.md` or outside the repository) and logs as they go.
- Minimum per entry: date, tool, task, 1–3 representative prompts (original language), how the output was used (as is, edited, starting point) and that it was checked.
- For the report, the logs are merged into the "Use of generative AI" section; non-English prompts get an English translation in the appendix.

## 10. Open questions

- Chair's report template: download and add to `../Informations/`.
- Presentation room (to be announced).
- How detailed the GenAI documentation should be: ask the supervisor in the proposal email if unclear.
- Names and matriculation numbers of all three members (needed for the proposal).
- GitHub repository visibility: private with collaborators during the project, public (or supervisor access) at submission? Check what the course expects.

## 11. How the topic was chosen (4 Nov 2026)

Criteria: clear prediction target, enough data, clean license, no textbook dataset, practical relevance, and above all data that is easy to understand. Rejected: Uber/Lyft prices, French bakery sales, ImmoScout24 rents, NYC restaurant inspections, BASt Autobahn counts, MaStR. Shortlist: Munich bicycle counters, German electricity demand (fallback), Deutsche Bahn delays (chosen). Details: decision log D1.

## 12. Sources

- [Deutsche Bahn Data on Hugging Face](https://huggingface.co/datasets/piebro/deutsche-bahn-data) — monthly Parquet files, CC BY 4.0
- [deutsche-bahn-data project on GitHub](https://github.com/piebro/deutsche-bahn-data) — collection method, local-time timestamps, coverage change on 2 Nov 2025, collection gaps Nov 2025 – Jul 2026
- [Arverio (Wikipedia)](https://en.wikipedia.org/wiki/Arverio); [Arverio BW construction notice RE 8, 21 Dec 2025 – 6 Feb 2026](https://www.arverio-bw.de/fileadmin/user_upload/Arverio_Baden-Wuerttemberg/Fahrplanabweichungen/141b_ABW_UPDATE_Baustelle_RE8_21.12.-06.02.26_Wuerzburg-Lauda.pdf)
- Grinsztajn, L., Oyallon, E., Varoquaux, G. (2022). *Why do tree-based models still outperform deep learning on tabular data?* NeurIPS Datasets and Benchmarks Track.
- Ke, G. et al. (2017). *LightGBM: A Highly Efficient Gradient Boosting Decision Tree.* NeurIPS.
- Assignment brief "Final Project: Your Own End-to-End Machine Learning Project", PDS course room, WiSe 2026/27
- Own data checks: `check_db.py`, `check_old.py` (outside the repository, `../pds-db-check/`); `checks/*.py` in this repository
- To add when used: weather source (Open-Meteo, CC BY 4.0), `holidays` package, school holiday list source
