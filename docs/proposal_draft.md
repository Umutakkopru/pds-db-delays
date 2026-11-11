# Topic proposal (draft)

> Draft of 10 Nov 2026 for the two-page proposal (deadline 30 Nov 2026, planned submission ~20 Nov). The text below the line is the proposal; it has about 700 words including the model table; check that it fits on two pages in the submission format. Before submitting: fill in the three names and matriculation numbers (they are not stored in the repository), let the group confirm decisions D1–D25, and copy the text into the submission form or template. All numbers come from `reports/checks/cleaning_counts.csv` and `reports/results_validation.md`.

---

## Will my train leave on time? Predicting departure delays at Würzburg Hbf before the trip and en route

**Group 18:** [Name 1, matriculation number] · [Name 2, matriculation number] · [Name 3, matriculation number]

### Problem statement

Delayed trains are an everyday problem for passengers in Germany, and a missed connection usually starts with a late departure. We predict, for every train departing Würzburg Hbf, the probability that it leaves **6 or more minutes late**. Six minutes is the threshold Deutsche Bahn uses in its punctuality statistic (there for arrivals); we apply it to departures because that is what a passenger waiting at the station experiences.

We make the prediction at two moments and compare them:

- **Scenario A, before the trip:** asked the day before, using only the timetable, the calendar, weather and past delay rates.
- **Scenario B, en route:** asked when the train leaves its previous stop, using in addition the delay the train already has.

The comparison answers a question of its own: how much of a delay is predictable in advance, and how much only becomes visible on the way?

### Dataset

- **Source:** Deutsche Bahn Data archive (`piebro/deutsche-bahn-data` on Hugging Face), collected four times a day from Deutsche Bahn's public Timetables API. **License:** CC BY 4.0 (Deutsche Bahn). It contains no personal data and is not a textbook dataset.
- **Size:** 28 monthly files, July 2024 – October 2026, about 15 million stop events per month for Germany since November 2025. For Würzburg Hbf: 365,502 stop events, of which 247,716 are planned departures. After excluding cancelled departures, rail replacement buses and rows without a timetable record, **230,333 departures** remain for modelling.
- **Additional sources:** hourly weather (Open-Meteo, CC BY 4.0) and public and school holidays in Bavaria.
- **Data checks already done:** no missing months and no duplicates; small stations before Würzburg are in the archive only from November 2025, so scenario B is trained from 3 November 2025; category labels that change over time (line names, operator label) are harmonised.

### Target variable and evaluation

- **Target:** `delayed = 1` if the departure delay is 6 minutes or more, else 0 (binary classification). In the training and validation period 24.8% of departures are delayed (regional trains 8.5%, long-distance trains 48.8%).
- **Split:** chronological, never random. Scenario A: training July 2024 – December 2025, validation January – June 2026, test July – October 2026. The test period is used once, at the very end, for all models at the same time.
- **Metrics:** primary **PR-AUC** (the positive class is the minority); in addition ROC-AUC, F1, precision and recall at a threshold chosen on validation, and the Brier score with a reliability diagram. Model differences are judged with a paired bootstrap that resamples whole days (95% interval), because departures of one day are not independent. Results are reported per service type and include an error analysis.

### Baselines and modelling approaches

| Model | Description | Role |
| --- | --- | --- |
| B0 | Always "on time" | Shows why accuracy misleads |
| B1 | Historical delay rate of service type × hour | Simple rule-based baseline |
| B2 | Logistic regression on timetable and calendar features | Interpretable baseline |
| B3 | "Late at the previous stop → late at Würzburg" | Baseline for scenario B |
| M-A | LightGBM, scenario A features | Main model, before the trip |
| M-A′ | LightGBM, scenario A features, scenario B training period | Control model |
| M-B | LightGBM, scenario A features plus delays at earlier stops | Main model, en route |

The control model M-A′ separates the effect of the en-route information (M-B − M-A′) from the effect of the shorter training period. Gradient-boosted trees are chosen because the data is tabular, with interactions (service × hour × weather), missing values and categorical features.

The data pipeline (DuckDB/SQL and Python) up to the weather and holiday tables, the evaluation code and the baselines B0–B2 already exist. On validation, B1 reaches a PR-AUC of 0.513 and B2 of 0.535 (ROC-AUC 0.785 and 0.800), so the advanced models have a clear bar to beat.

**Planned extensions:** explanations with SHAP, and a small Streamlit dashboard that replays real departures of the test period with the predicted probability and its explanation. Data leakage is addressed by a feature whitelist, automated tests and the rule that scenario A never sees information from the day of the trip (weather is the stated exception: observed weather stands in for a forecast).

---

## To send with the proposal (not part of the two pages)

Question to the supervisor: the brief asks for a section on the use of generative AI "stating which parts of the work it was used for and the prompts used". Is a table with one to three representative prompts per task sufficient, or should all prompts be listed (for example in an appendix)?

## Checklist before submitting

- [ ] Names and matriculation numbers of all three members filled in
- [x] Group registered in the course room (hard deadline 15 Nov 2026)
- [ ] Decisions D1–D25 confirmed by the group (B3 and the control model are named in the proposal)
- [ ] Numbers still equal `reports/checks/cleaning_counts.csv` and `reports/results_validation.md`
- [ ] Length checked in the submission format (maximum two pages)
