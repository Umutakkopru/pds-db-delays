# Report section 4: Methodology (draft)

> Draft of 11 Nov 2026 for section 4 of the final report (planned length 3–4 pages, `docs/project_plan.md` section 7). The text between the two lines is the section: about 1,650 words of text and three tables; 4 pages in the plain PDF layout (`docs/pdf/report_methodology_section.pdf`). Decisions D1–D25 are proposals until the group confirms them; if a decision changes, the matching paragraph changes with it. The section describes the method only: scores, chosen settings and the outcomes of the sanity checks belong to section 5 and are not repeated here. Every statement is traced to code or to the decision log in "Where the statements come from" at the end. Citations are written as [Author year] and are replaced by the template's citation style.

---

## 4 Methodology

### 4.1 Prediction task

For every train departure at Würzburg Hbf we predict the probability that it leaves 6 or more minutes late (`delayed = 1`, section 3.4). We treat this as binary classification and not as a regression on minutes, because the delay distribution is strongly skewed (section 3.7) and the passenger's question, whether a connection can be reached, is a yes-or-no question.

The prediction is made at two moments (Table 6). Comparing them answers how much of a delay is predictable in advance and how much only becomes visible on the way.

**Table 6.** The two prediction scenarios.

| | Scenario A: before the trip | Scenario B: en route |
| --- | --- | --- |
| Moment | The day before the departure | When the train leaves its previous stop |
| Applies to | All departures | Through trains with an earlier stop in the data |
| Information | Timetable, calendar, weather, delay rates of the last four weeks | Everything in A, plus the delay at the stops already passed |

### 4.2 Pipeline

The work is one pipeline of seven scripts (download and filter, clean, enrich, features, train and evaluate, error analysis, explanations) that runs from the raw monthly files to the result tables with one command, in about two minutes after the download. Data preparation is written in SQL (DuckDB), modelling in Python (scikit-learn, LightGBM [Ke et al. 2017]). Split dates, thresholds and the random seed are defined in one configuration file, and LightGBM runs in its deterministic mode, so a second run gives identical numbers.

### 4.3 Features

Scenario A uses 21 features, scenario B the same 21 plus 4 (Table 7). Models may only read columns on an explicit list; a second list names the columns that must never be used (section 4.7).

**Table 7.** Features by group.

| Group | Features | Scenario |
| --- | --- | --- |
| Timetable (8) | Service, line, destination, planned hour, weekday, through train or not, position of the stop in the route, planned stop time at Würzburg | A, B |
| Calendar (3) | Public holiday, school holiday, bridge day | A, B |
| Weather (6) | Temperature, precipitation, wind speed, wind gusts, snowfall, snow depth in the planned departure hour | A, B |
| History (4) | Delay rate of the last 28 days for the same service and hour, for the same route, and for all departures; number of departures on the route in that window | A, B |
| Previous stops (4) | Delay at the last and at the second-to-last earlier stop, planned minutes from the last earlier stop to the Würzburg departure, number of stops in between | B only |

**History.** For a departure on day D the history covers the days D − 29 to D − 2. Day D − 1 is left out on purpose: scenario A is asked the day before, when that day is not yet complete. "Route" is the line for regional trains and the destination for the other trains, which have no line number. A rate is set to missing if its window holds fewer than 20 departures. History is computed from modelling rows only. It is also computed inside the validation and test periods, from the outcomes of earlier days, as a system in use would do.

**Previous stops.** The last earlier stop is the latest stop of the same trip that is planned before the arrival at Würzburg, is not cancelled and has a reported time. Its delay is the departure delay, or the arrival delay if the stop has no departure.

**Left out on purpose.** The raw train type (its labels change, section 3.3), the train number, month and year (the models should not memorise periods), and all flags that the source sets only once a disruption is known; these flags filter rows and are never features.

**Weather is observed, not forecast.** In scenario A the weather of the departure hour stands in for a forecast that would be available the day before. This favours scenario A slightly. We bound the effect by training the scenario A model once without the weather features (section 5).

### 4.4 Split

The split is chronological and never random (Table 3 in section 3.6): a model is always evaluated on departures that lie after everything it was trained on, as in real use. A random split would put departures of the same day, with the same disruptions, on both sides.

- **Scenario A:** training July 2024 – December 2025, validation January – June 2026 (it contains a winter), test July – October 2026.
- **Scenario B:** training 3 November 2025 – April 2026, validation May – June 2026, the same test period. It starts later because the earlier stops of regional trains are in the data only from that date (section 3.3).

The test period is the most recent data and is used once (section 4.6). Its limitation is that it contains no winter.

### 4.5 Models

**Table 8.** Baselines and models.

| ID | Model | Trained on | Purpose |
| --- | --- | --- | --- |
| B0 | Always "on time" (constant probability) | – | Shows why accuracy misleads |
| B1 | Delay rate of service × hour in the training data | A training | Rule-based baseline |
| B2 | Logistic regression on one-hot timetable and calendar columns | A training | Interpretable baseline |
| B3 | "6 or more minutes late at the previous stop → delayed" | nothing is fitted | Baseline for scenario B |
| M-A | LightGBM, scenario A features | A training | Main model, before the trip |
| M-A′ | LightGBM, scenario A features | B training | Control model |
| M-B | LightGBM, scenario B features | B training | Main model, en route |

**Baselines.** B1 falls back to the rate of the service when a service-hour cell has fewer than 30 training departures. B3 needs no training: its class rule is the 6-minute threshold applied to the previous stop, and its ranking score is the previous-stop delay in minutes. M-B is useful only if it beats this rule.

**Main model.** We use gradient-boosted decision trees (LightGBM). They are the established strong choice for tabular data [Grinsztajn et al. 2022], learn interactions such as service × hour without hand-built terms, and handle missing values and categorical features directly. Category lists are taken from the training rows; a category that appears only later is treated as missing. We use no class weights, so that the predicted probabilities stay calibrated; the class threshold handles the imbalance instead.

**Control model.** M-A is trained on 18 months of all departures, M-B on 6 months of through trains. The difference between them would mix two things: the previous-stop information, and a different training period and row set. M-A′ has the features of M-A and the training rows of M-B. The effect of the previous-stop information is M-B − M-A′; the effect of the training period is M-A′ − M-A.

### 4.6 Tuning, final models and the single test run

**Tuning.** Each LightGBM model is tuned over the same grid of 12 settings, fixed before the first run: four tree sizes (7, 15, 31, 63 leaves) with two minimum leaf sizes, LightGBM's default setting, and three regularised variants. The learning rate is 0.05. The number of trees is set by early stopping (50 rounds) on the validation log loss, and the setting with the best validation PR-AUC is kept. The class threshold is the value that maximises F1 on validation.

**Final models.** All models, baselines included, are then fitted again on training plus validation rows, with the setting, the number of trees and the threshold unchanged, and scored once on the test period.

**One run, technically enforced.** The test period is used by a single command. It writes a marker file with the time and the code version and refuses to start if the marker exists or if the code has uncommitted changes. Outside this command no function of the pipeline returns rows of the test period. Features, tuning, error analysis and explanations were developed on validation data only.

**What was seen of the test period before.** The first data checks, made before this rule was set, covered all 28 months in aggregate: rows per day, cancellation shares and delay rates per month, and the delay rate by train type in October 2026. These aggregates informed the choice of topic and the cleaning rules. No feature, model, setting or threshold was chosen with them, and from the cleaning step on no delay statistic of the test period was computed.

**Rehearsal.** Validation scores are optimistic, because the same rows stop the training, choose the setting and choose the threshold. Before the final run we therefore ran the whole final procedure one step back in time, with the validation period in the role of the test set. This checks the final code on real data and measures the optimism without touching the test period (section 5).

### 4.7 Evaluation

**Metrics.** The primary metric is PR-AUC, because the positive class is the minority (22–26% of all departures) and PR-AUC is not flattered by the many easy negatives. We also report ROC-AUC; F1, precision and recall at the validation threshold; and the Brier score with a reliability diagram for the quality of the probabilities. Accuracy is shown only next to B0. Because one threshold over all departures suits the frequently delayed long-distance trains, we also report the class metrics with a threshold per service, chosen on validation in the same way.

**Uncertainty.** Departures of one day share weather and disruptions and are not independent. Intervals therefore come from a bootstrap that resamples whole days (1,000 resamples). Two models are compared on the same resamples, and one counts as better only if the 95% interval of the difference lies above zero.

**Same rows.** Row sets with different delay rates are not compared with each other. B0, B1, B2 and M-A are scored on all departures; M-A, M-A′, B3 and M-B on the identical scenario B rows.

**Beyond the overall score.** Because the service dominates the delay rate (section 3.7), all results are also reported per service and by further slices (line, hour, month, weather; scenario B also by the planned time since the previous stop), and the 20 largest errors of each model are grouped into failure types. Two sensitivity checks repeat the evaluation with the rows that cleaning set aside: cancelled departures counted as delayed, and departures without a timetable record included. SHAP values [Lundberg and Lee 2017] show which features the models rely on.

### 4.8 Data leakage: rules and safeguards

A model that sees information from the future looks good in the evaluation and fails in use. In this project the risk is high, because the realised times sit in the same row as the features. The rules are: realised times and delays at Würzburg are never features; history ends two days before the departure; scenario B uses only stops that the train has already passed; category lists, encoders and rates are fitted on training rows and the threshold on validation rows; disruption flags only filter rows. Observed weather is the one stated exception (section 4.3). Rules alone do not protect against mistakes, so four safeguards check them:

- **Feature lists.** Models read exactly the columns on the allowed list. Every raw column of the source is classified as allowed or forbidden; a new, unclassified column fails a test.
- **Automated tests.** 175 tests run before every training run. The most important one is a time-travel test: changing every outcome from day D − 1 on must leave the features of day D unchanged, while changing day D − 2 must change them. Other tests check that the splits are chronological and disjoint, that scenario A has no previous-stop feature, that the previous stop lies before the Würzburg arrival, that scenario B rows carry exactly the scenario A feature values (so that all models are scored on identical rows), and that the test period cannot be loaded outside the final run. We also tested the tests: widening the history window by one day on purpose makes six of them fail.
- **Sanity checks on results.** No single scenario A feature may reach a ROC-AUC of 0.9 on its own. A model trained on shuffled labels must score a ROC-AUC of about 0.5. A scenario A ROC-AUC above 0.95 would be treated as a leak, not as a success. The most important features must make domain sense.
- **Review.** Feature and split code is read by a second group member.

One selection remains: cancelled departures are excluded, although a cancellation is known only afterwards. The target is undefined for a train that does not run; the first sensitivity check measures the effect.

---

## Where the statements come from

| Statement | Source |
| --- | --- |
| Target, scenarios, split | Decision log D2, D3, D4, D6; `SPLITS` in `src/config.py` |
| Pipeline steps, seed, deterministic mode | `run_pipeline.py`; `src/config.py`; `BASE_PARAMS` in `src/models.py` |
| Feature lists and groups (21 and 25) | `src/features_config.py`; D24 |
| History window, minimum of 20 departures | `HISTORY_FIRST_DAY_BACK`, `HISTORY_LAST_DAY_BACK`, `MIN_HISTORY_ROWS` in `src/config.py`; `src/sql/04_features.sql` |
| Previous stops | `src/sql/04_features_b.sql`; D12, D20 |
| Features left out | D7, D14, D16, D24 |
| Baselines (fallback below 30 rows, one-hot, no class weights) | `src/baselines.py`; D14, D17 |
| Control model | D13 |
| Grid of 12 settings, learning rate, early stopping | `TUNING_GRID`, `BASE_PARAMS`, `EARLY_STOPPING_ROUNDS` in `src/models.py`; D21 |
| Refit, single run, marker file, rehearsal | `src/05_train.py`; `REHEARSAL_SPLITS` in `src/config.py`; D21, D25 |
| Metrics, day-block bootstrap, paired differences | `src/evaluate.py`; D13 |
| Slices, failure types, sensitivity checks, SHAP | `src/06_error_analysis.py`, `src/07_explain.py`; D9, D18 |
| Leakage rules and safeguards; 175 tests; six tests fail when the window is widened | `src/features_config.py` (whitelist); `tests/`; D24 |

## Open points before this goes into the template

- [ ] Group confirms D1–D25 (this section rests on D2–D6, D13, D14, D16, D17, D20, D21, D24, D25).
- [ ] **"Review" in 4.8 is not true yet:** no second member has read the feature and split code so far. Either the review happens before submission, or the sentence is removed.
- [ ] References in the template's style: [Ke et al. 2017] and [Grinsztajn et al. 2022] are in the "Sources" list of `docs/decision_log.md`; [Lundberg and Lee 2017] (SHAP) was added there on 11 Nov 2026. Check all three against the original papers before submission.
- [ ] The sentence on thresholds per service in 4.7 is proposal P1 (`docs/group_decision_sheet.md`); remove it if the group rejects P1.
- [ ] Table numbers continue from section 3 (Tables 1–5); renumber if section 3 is shortened.
- [ ] After the final run: check that "175 tests" (updated from 151 on 16 Nov 2026) and "about two minutes" are still right.
- [ ] The horizon bin "10–20 min" of the error analysis is called "up to 20 min" in the report: the test period has 149 scenario B rows with 7–9 planned minutes from the previous stop (review finding E-03).
- [ ] E-01 (scenario B rows whose outcome is already certain at the prediction moment) and E-02 (reading of M-A − B2 as model plus features) wait for a group decision.
- [ ] **Length.** If it has to shrink to 3–4 pages, cut first: the pipeline paragraph (4.2) down to two sentences with a link to the repository; "Left out on purpose" in 4.3 down to one sentence; the numbered list of rules in 4.8 (the safeguards carry the content).
- [ ] Optional figure if space allows: a timeline of the two splits and the history window (none is included now).
