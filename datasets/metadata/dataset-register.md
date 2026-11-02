# Dataset register

Raw files live in `datasets/raw/` (gitignored) and are never modified. Verify them with `sha256sum`.

| ID | Dataset | Role | Local file | Size (bytes) | SHA-256 | Source | Obtained | Licence | Caveat |
|---|---|---|---|---|---|---|---|---|---|
| A | MetroPT-3 (UCI #791) | Equipment time series (APU compressor, 1 Hz) | `raw/metropt+3+dataset/MetroPT3(AirCompressor).csv` | 218300507 | `db30ccb4ea402e3c8bf2c99db06e288d4f2a772f6928f9dbe26a920d69793e24` | https://archive.ics.uci.edu/dataset/791/metropt%2B3%2B | ≤2026-11-01 | CC BY 4.0 (verify) | 4 air-leak reports; not row-labelled |
| A-doc | MetroPT-3 description | Failure-window reference | `raw/metropt+3+dataset/Data Description_Metro.pdf` | 81208 | `b00fac0e8899854078309bef4adaa480d82ecf14dc81c5097c3646973e824127` | as above | ≤2026-11-01 | as above | |
| B | Train track environmental (Zenodo 17607068) | Vibration/GPS anomaly exploration (40 Hz nominal) | `raw/vibration_raw.csv` | 65561577 | `fcd58729a7c3bee7e970c3b5a29133d6be39f953fcbb98358f4ea5c187830abd` | https://zenodo.org/records/17607068 | ≤2026-11-01 | see record JSON | An anomaly is not an inspected defect |
| B-meta | Zenodo record metadata | Provenance | `raw/17607068.json` | 29204 | `b549082d4582626065e52c6c594179cde35017488319cd8aebb031db60a937a3` | as above | ≤2026-11-01 | | |
| C | FRA Form 54, human-readable view (85tf-25kj) | Historical accident analysis | `raw/Rail_Equipment_Accident_Incident_Data_(Form_54)_20261101.csv` | 305392655 | `031ce299c3aa029dd985ab147b3daa8071a0b4173dfe683fb05390b0a9dae5cb` | https://data.transportation.gov/Railroads/Rail-Equipment-Accident-Incident-Data-Form-54-/85tf-25kj | 2026-11-01 | US public data (verify terms) | Reporting threshold; multiple reports per accident; post-event fields; US context |
| D | Synthetic simulator | Operational conflict tests | generated | n/a | n/a | this repo | n/a | MIT | Synthetic, not operational evidence |

Pending: the FRA data dictionary PDF and the raw Source Table (aqxq-n5hy) have not been downloaded yet. Confirm the licences in Phase 1, 3 and 4.
