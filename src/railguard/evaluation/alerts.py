"""Turn a score series into alert episodes (spec 002)."""

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class AlertEpisode:
    """Consecutive alerts merged into one episode, from first to last alert time."""

    start: pd.Timestamp
    end: pd.Timestamp
    peak_score: float


def alert_episodes(
    scores: pd.Series,
    threshold: float,
    merge_gap: pd.Timedelta,
    segment_ids: pd.Series,
) -> list[AlertEpisode]:
    """Group rows with ``score > threshold`` into episodes.

    ``scores`` is indexed by timestamp (sorted) and ``segment_ids`` shares that index. Alerts
    at most ``merge_gap`` apart join the same episode, but an episode never crosses a
    segment boundary. Episodes are returned in start order.
    """
    if not scores.index.equals(segment_ids.index):
        raise ValueError("scores and segment_ids must share the same index")
    hits = scores[scores > threshold]
    episodes: list[AlertEpisode] = []
    for _, group in hits.groupby(segment_ids.loc[hits.index], sort=True):
        episodes.extend(_merge(group, merge_gap))
    return sorted(episodes, key=lambda e: e.start)


def _merge(alerts: pd.Series, merge_gap: pd.Timedelta) -> list[AlertEpisode]:
    times = pd.DatetimeIndex(alerts.index)
    new_episode = pd.Series(times).diff() > merge_gap
    episode_ids = new_episode.cumsum().to_numpy()
    values = alerts.to_numpy()
    out: list[AlertEpisode] = []
    for episode_id in sorted(set(episode_ids)):
        chosen = episode_ids == episode_id
        out.append(
            AlertEpisode(
                start=times[chosen][0],
                end=times[chosen][-1],
                peak_score=float(values[chosen].max()),
            )
        )
    return out
