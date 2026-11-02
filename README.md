# RailGuard AI

Railway safety intelligence, predictive maintenance and simulated collision-risk monitoring. This is an academic and portfolio **research prototype**.

> **Safety statement:** RailGuard AI is a decision-support research prototype. It must not connect to or issue commands to real railway control equipment. ML outputs never override the deterministic rule engine. Simulated data is always labelled synthetic.

## Motivation
Recent high-speed rail collisions have been attributed to signalling failures combined with control-centre human error. No public dataset offers synchronised train positions, signals and movement authorities that could be used to "predict" such an event. RailGuard AI therefore splits the problem in two:
- **ML** handles what the public data supports: equipment and track anomaly detection, and historical accident patterns.
- **A deterministic, tested rule engine** runs over a transparent simulator. It covers signalling and authority conflicts such as a train approaching an occupied block or passing a restrictive signal.

## Capabilities (planned)
1. **Equipment health:** anomaly detection on MetroPT-3 compressor sensors.
2. **Track condition:** vibration anomaly exploration with GPS context (Zenodo 17607068).
3. **Historical safety analytics:** descriptive analysis of FRA Form 54.
4. **Operational conflict monitor:** a synthetic train simulator with a deterministic, tested rule engine.

## Setup
```powershell
uv venv .venv --python 3.12
uv pip install --python .venv\Scripts\python.exe -e ".[dev,analysis]"
.venv\Scripts\python -m pytest
```
Place the raw datasets in `datasets/raw/` as listed in [dataset-register.md](datasets/metadata/dataset-register.md), then verify the checksums.

## Project docs
- [Master document](docs/RailGuard_AI_Project_Master_Document.docx): the source of truth
- [AGENTS.md](AGENTS.md): workflow, branches, conventions
- [specs/](specs/): spec-driven phase specs
- [DEVLOG](docs/logs/DEVLOG.md) · [CHANGELOG](CHANGELOG.md) · [Decisions](docs/decisions/) · [Risks](docs/risk-register.md)

## Licence
MIT. See [LICENSE](LICENSE). Datasets keep their own licences.
