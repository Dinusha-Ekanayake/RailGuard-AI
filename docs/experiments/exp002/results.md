# EXP-002 results

| Model | Variant | Split | Events with an alert | Lead time per event (h) | Alerts outside windows per operating hour | Threshold |
|---|---|---|---|---|---|---|
| E0 | all | validation | 1 of 2 | #1: none, #2: 5.12 | 0.0291 | 15191.530442 |
| E0 | all | test | 2 of 2 | #3: 21.53, #4: 15.40 | 0.0743 | 15191.530442 |
| E1 | all | validation | 2 of 2 | #1: -1.20, #2: -0.02 | 0.0118 | 0.665700 |
| E1 | all | test | 2 of 2 | #3: -0.10, #4: 6.00 | 0.0058 | 0.665700 |
| E0 | no_oil_level | validation | 1 of 2 | #1: none, #2: 5.12 | 0.0291 | 15191.530442 |
| E0 | no_oil_level | test | 2 of 2 | #3: 21.53, #4: 15.40 | 0.0743 | 15191.530442 |
| E1 | no_oil_level | validation | 2 of 2 | #1: -1.20, #2: -0.03 | 0.0097 | 0.674443 |
| E1 | no_oil_level | test | 2 of 2 | #3: -0.11, #4: 6.00 | 0.0058 | 0.674443 |

An event counts as having an alert when an alert episode overlaps [start - horizon, end]. Lead time is measured from the first alert in that range to the window start (negative after it began). Alerts outside documented windows are an upper bound on false alerts: windows are approximate and other anomalies may exist.

## Plots

- plots/E0_all_event1.png
- plots/E0_all_event2.png
- plots/E0_all_event3.png
- plots/E0_all_event4.png
- plots/E1_all_event1.png
- plots/E1_all_event2.png
- plots/E1_all_event3.png
- plots/E1_all_event4.png
- plots/E0_no_oil_level_event1.png
- plots/E0_no_oil_level_event2.png
- plots/E0_no_oil_level_event3.png
- plots/E0_no_oil_level_event4.png
- plots/E1_no_oil_level_event1.png
- plots/E1_no_oil_level_event2.png
- plots/E1_no_oil_level_event3.png
- plots/E1_no_oil_level_event4.png
- plots/alerts_outside_per_hour.png
- plots/events_with_alert.png
