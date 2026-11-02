# ADR-0002: MetroPT-3 window sizes and gap policy at 10 s sampling

- **Status:** Accepted
- **Date:** 2026-11-02

## Context
The master doc (§5.1) proposes 10 s and 30 s rolling windows, assuming 1 Hz data. The real file has a median sampling interval of 10 s (p1 9 s, p99 12 s), confirmed by the UCI page (0.1 Hz). Such windows would hold 1 to 3 samples. The file also has 331 gaps longer than 60 s (160 longer than 1 h, longest about 48 h).

## Decision
- Candidate rolling-window sizes are **60 s, 5 min, 15 min and 60 min** (6, 30, 90 and 360 samples).
- Operating segments are split wherever the gap between consecutive timestamps is **greater than 60 s** (configurable; a gap of exactly 60 s stays in the segment).
- **No interpolation across gaps.** Windows never span a segment boundary.
- The pre-event horizon (default 24 h) is a configurable assumption, not a fact.

## Alternatives considered
- Keep 10 s and 30 s windows: too few samples for stable statistics.
- Interpolate or forward-fill across gaps: invents data and hides downtime that may be informative.
- A larger gap threshold (for example 5 min): would bridge outages the sampler clearly missed.

## Consequences
- Phase 2 feature code must respect `segment_id` when computing windows.
- Segments shorter than a window yield no features for that window size.
- The threshold and window set can be revisited by a new ADR once Phase 2 shows their effect.
