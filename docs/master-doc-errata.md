# Master document errata

Corrections to `docs/RailGuard_AI_Project_Master_Document.docx` (v1.0). The .docx is not edited in place; this file is the record until a v1.1 is issued. Specs and code follow the corrected value.

| ID | Section | Master doc says | Correct value | Evidence | Where handled |
|---|---|---|---|---|---|
| E-01 | §5.1 | MetroPT-3 sampled at 1 Hz, about 15.2 M rows | 10 s (0.1 Hz), 1,516,948 rows | UCI dataset page; local profile | Spec 001, dataset card |
| E-02 | §5.1 | Rolling windows of 10 s and 30 s | 60 s, 5 min, 15 min, 60 min | 10 s sampling leaves 1 to 3 samples per window | ADR-0002 |
| E-03 | §19 | Paper DOI `10.1109/DSAA53316.2021.9564201` | `10.1109/DSAA53316.2021.9564181` | The old DOI returns 404; the new one resolves to the paper | Dataset card |
| E-04 | §5.1 | Data spans Feb to Aug 2020 | 2020-02-01 to 2020-09-01 03:59:50 | Local profile | Dataset card |
| E-05 | §7.2 | Candidate pre-event horizons of 10, 30 and 60 min | Still candidates; the 24 h default in specs 001 and 002 is also an assumption | Design choice, not a fact | Spec 002 |
