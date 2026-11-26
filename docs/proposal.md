# Topic proposal

> Proposal for submission (deadline 30 Nov 2026, maximum two pages). The text between the two lines is the proposal. Names and matriculation numbers are filled in only in the submitted PDF, not in the repository. Numbers: `reports/checks/monthly_summary.csv`, `reports/checks/cleaning_counts.csv`.

---

## Will my train leave on time? Predicting departure delays at Würzburg Hbf before the trip and en route

**Group 18:** [Name 1, matriculation number] · [Name 2, matriculation number] · [Name 3, matriculation number]

### Problem statement and motivation

Delays are an everyday problem for rail passengers in Germany, and a missed connection usually starts with a late departure. We want to predict, for every train departing Würzburg Hbf, the probability that it leaves **6 or more minutes late**. Six minutes is the threshold of Deutsche Bahn's punctuality statistic (defined there for arrivals); we apply it to departures, because that is what a passenger waiting on the platform experiences.

We plan to make the prediction at two moments and to compare them:

- **Scenario A, before the trip:** asked the day before, with information that is known in advance: timetable, line and service type, calendar and holidays, weather and recent delay rates.
- **Scenario B, en route:** asked when the train leaves its previous stop, with the delay it has already accumulated in addition.

The comparison raises a question of its own: how much of a departure delay can be predicted in advance, and how much only becomes visible on the way? The answer matters for passengers planning a connection and for how a travel app should communicate risk.

### Dataset

- **Source:** the Deutsche Bahn Data archive on Hugging Face (`piebro/deutsche-bahn-data`), collected four times a day from Deutsche Bahn's public Timetables API and published as one Parquet file per month. **License:** CC BY 4.0 (Deutsche Bahn). The data contains no personal information and is not a standard teaching dataset.
- **Size:** 28 monthly files from July 2024 to October 2026, up to about 15 million stop events per month for all of Germany. A first look at Würzburg Hbf gives 365,502 stop events, about 248,000 of them planned departures, with planned and actual times, train type, line, destination and cancellation flags.
- **Additional sources:** hourly historical weather at Würzburg (Open-Meteo, CC BY 4.0) and Bavarian public and school holidays (official announcement).
- **Known challenges:** cancellations and rail replacement buses have to be separated from regular departures; line and operator labels change over the period; small stations before Würzburg appear in the archive only from November 2025, which limits the period available for scenario B.

### Target variable and evaluation

- **Target:** `delayed = 1` if the departure is 6 or more minutes after the planned time, else 0 (binary classification). Roughly a quarter of departures are delayed, with large differences between regional and long-distance trains.
- **Split:** chronological, never random, so that every model predicts a later period than it was trained on. Planned for scenario A: training July 2024 – December 2025, validation January – June 2026, test July – October 2026. The test period is used once, at the end, for all models at the same time.
- **Metrics:** primary **PR-AUC**, because the delayed class is the minority; in addition ROC-AUC, F1, precision and recall at a threshold chosen on the validation data, and the Brier score for calibration. Differences between models will be judged with a bootstrap that resamples whole days, because departures on the same day are not independent.
- **Error analysis:** results per service type, line, hour and weather condition, calibration, and the largest errors.

### Planned baselines and modelling approaches

| Model | Description | Role |
| --- | --- | --- |
| B0 | Always "on time" | Shows why accuracy misleads |
| B1 | Historical delay rate of service type × hour | Rule-based baseline |
| B2 | Logistic regression on timetable and calendar features | Interpretable baseline |
| B3 | "Late at the previous stop → late at Würzburg" | Simple rule for scenario B |
| M-A | Gradient-boosted trees (LightGBM), scenario A features | Main model before the trip |
| M-B | LightGBM, scenario A features plus delays at earlier stops | Main model en route |

We choose gradient-boosted trees as the advanced approach because the data is tabular, delay risk depends on interactions (service type × hour × weather), earlier-stop information is missing for trains that start at Würzburg, and line and destination are categorical. To separate the value of the en-route information from the shorter training period of scenario B, we plan an additional control model with scenario A features trained on the scenario B period.

**Data leakage** is a central risk: the actual departure time at Würzburg and anything derived from it must never become a feature, and recent delay rates may only use days before the prediction. We plan a feature whitelist and automated tests for these rules.

**Planned extensions:** feature attributions with SHAP, and a small Streamlit dashboard that shows the predicted delay risk for a line, day and hour, with and without a known delay at the previous stop.

---
