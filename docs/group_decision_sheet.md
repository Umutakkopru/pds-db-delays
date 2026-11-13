# Group decision sheet: D1–D25 and three open proposals

One-page-per-topic summary for the group meeting. All 25 decisions were prepared by one member and are **proposals** until the group has confirmed them. Details, evidence and alternatives: `docs/decision_log.md` (same numbers). The single final run on the test period waits for this confirmation, because nothing may change afterwards.

**How to use it.** Go through the tables together. For each row write one of: **OK** (confirmed), **Change:** what instead, **Open:** what is unclear. Rows marked ★ have a real alternative and deserve a short discussion; the others follow from the data checks. Afterwards one member records the result (section "How the result is recorded").

## A. Problem and data

| # | Decision | Group |
| --- | --- | --- |
| D1 | Topic: departure delays at Würzburg Hbf, open Deutsche Bahn archive (CC BY 4.0), July 2024 – October 2026 | |
| ★ D2 | Target: delayed = departure 6 or more minutes late (DB's threshold, defined by DB for arrivals, applied to departures); classification, not regression | |
| ★ D3 | Two scenarios: A the day before; B when the train leaves its previous stop (through trains only) | |
| D7 | `line_id` and `service` instead of the raw train type (labels change in December 2025) | |
| D8, D19 | Excluded: replacement buses, rows without timetable record, nights of a clock change, impossible delays; rows are flagged, not deleted | |
| ★ D9 | Cancelled departures are excluded from the main target; a sensitivity check counts them as delayed | |
| D10, D23 | Local time everywhere; weather from Open-Meteo (downloaded in UTC), Bavarian public and school holidays, bridge days | |
| D11 | Target = last time reported by DB's API; no day excluded for collection gaps | |
| D12 | Earlier stops are searched within the same monthly file | |
| ★ D18 | Rows without timetable record stay excluded (delayed twice as often; share grows from 1.6% to 6.3%); a second sensitivity check includes them | |
| D20 | Scenario B rows = through trains with a usable earlier stop | |

## B. Split, models and features

| # | Decision | Group |
| --- | --- | --- |
| ★ D4 | Chronological split; test = July – October 2026 for both scenarios, used once (limitation: no winter in the test period) | |
| D5 | LightGBM as main model; baselines B0 (majority), B1 (service × hour), B2 (logistic regression) | |
| ★ D6 | Scenario B is trained from 3 November 2025 only (earlier stops of regional trains are missing before) | |
| ★ D13 | Control model M-A′ (scenario A features, scenario B training rows); models compared with a paired bootstrap over whole days; no class weights | |
| D14 | History features use days D − 29 to D − 2; the train number is a key, never a feature | |
| D16 | Disruption flags are filters, never features | |
| ★ D17 | Baseline B3 for scenario B: "late at the previous stop → late at Würzburg"; M-B must beat it | |
| D21 | Grid of 12 settings fixed in advance; tree count and threshold kept in the refit; weather ablation | |
| D24 | 21 features for scenario A, 4 more for scenario B | |

## C. Procedure, scope and plan

| # | Decision | Group |
| --- | --- | --- |
| ★ D25 | Final run = one command with a lock; rehearsal one step back in time; thresholds from validation | |
| D15 | Dashboard replays real departures of the test period; no free future dates | |
| D22 | Order of work; minimum version frozen 1 December, extensions 8 December, everything finished 15 December | |
| ★ – | Roles and report sections per member (`docs/project_plan.md` section 7) | |
| ★ – | Order of what is dropped if time is short (`docs/project_plan.md` section 5) | |

## D. Three open proposals (new, 11 Nov 2026; to decide before the final run)

They answer weaknesses seen on validation. None changes a model or a feature; P1 and P2 add reporting, P3 is a wording decision. Evidence is from the rehearsal (scored rows were not used for any choice).

| # | Weakness | Proposal | Group |
| --- | --- | --- | --- |
| P1 | With one overall threshold, M-A almost never flags a regional train (recall 0.6% on regional trains), although it does rank them: the 5% of regional departures with the highest score are delayed 21% of the time against 8.6% on average | Keep the overall threshold as the main operating point. Report in addition: precision, recall and F1 per service with a threshold chosen per service on validation (regional: recall 41%, precision 16%), and the delay rate of the top 5% and 10% per service. Coded on 13 Nov 2026 as an extra section of the results file; if the group rejects it, the section is removed | |
| P2 | The scenario B models are tuned by models that never saw a day above 21 °C; weather adds only about 0.001 PR-AUC to M-B | Keep the features. Done on 13 Nov 2026: the ablation is part of the training script (M-B +0.001 PR-AUC with weather, interval includes zero) | |
| P3 | The test period has no winter | Report the rehearsal scores (January – June 2026, with winter, unbiased) next to the test scores, and say so in the Discussion. No change of the test period | |

## How the result is recorded

1. Fill in the "Group" column (on paper, in the PDF or in this file) and note the date of the meeting.
2. Pass the result on in one message, for example: "Meeting of 14 Nov: all confirmed except D9 (change: …) and P1 (rejected)". Decisions without a remark count as confirmed.
3. The decision log then gets a line "Confirmed by the group on …" per decision, changed decisions get a dated note with the reason, and `CLAUDE.md` drops the word "proposals".
4. Only after that: `python src/05_train.py --final`.
