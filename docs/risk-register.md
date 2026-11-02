# Risk register

From master doc §16.1. Status: Open, Mitigating or Closed.

| ID | Risk | Mitigation | Status |
|---|---|---|---|
| R01 | Sparse or incomplete failure labels (MetroPT-3) | Anomaly detection, event-level evaluation, explicit uncertainty | Open |
| R02 | Time leakage | Chronological and event-aware splits; tests check that rolling features use no future data | Open |
| R03 | Vibration anomaly misread as a track defect | Neutral wording; no defect claims without inspection labels | Open |
| R04 | FRA post-event leakage | Define the prediction time; exclude post-event fields | Open |
| R05 | Historical data bias | Document reporting thresholds and exposure-denominator limits | Open |
| R06 | Synthetic data mistaken for real | `synthetic` flag in the DB, UI and exports | Open |
| R07 | ML mistaken for safety authority | Separate rule engine; ML cannot suppress rules; disclaimer | Open |
| R08 | Scope expansion | Finish the equipment anomaly vertical slice first | Open |
| R09 | Large data accidentally committed | `.gitignore` plus CI check that rejects files over 5 MB | Mitigating |
