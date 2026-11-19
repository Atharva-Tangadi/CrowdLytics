"""Explainable sudden-count-increase detector, not proof of an organized flash mob."""
from collections import deque
import math
import statistics


class CrowdIncreaseDetector:
    def __init__(self, config):
        self.config = config
        self.history = deque()
        self.state = "NORMAL"
        self.candidate = None
        self.event = None
        self.cooldown_until = 0.
        self.last_timestamp = None
        self.events = []

    def reset(self):
        self.history.clear()
        self.state = "NORMAL"
        self.candidate = self.event = None

    def update(self, timestamp, count, valid=True):
        c = self.config
        if (not valid or count is None or not math.isfinite(count) or count < 0
                or not math.isfinite(timestamp) or (self.last_timestamp is not None and timestamp <= self.last_timestamp)):
            self.reset()
            return {"state": "UNAVAILABLE", "reason": "Scene or count history is unreliable"}
        if self.last_timestamp is not None and timestamp - self.last_timestamp > c.max_gap_seconds:
            self.reset()
        self.last_timestamp = timestamp
        while self.history and timestamp - self.history[0][0] > c.window_seconds:
            self.history.popleft()
        if self.state in ("DETECTED", "COOLING_DOWN"):
            if count <= self.event["baseline_count"] + c.min_absolute * 0.5 and timestamp >= self.cooldown_until:
                self.state = "RESOLVED"
                self.events.append(dict(self.event, state="RESOLVED", timestamp=timestamp))
                self.history.clear()
                self.history.append((timestamp, count))
            else:
                self.state = "COOLING_DOWN"
            return dict(self.event, state=self.state, timestamp=timestamp, current_count=count,
                        absolute_increase=count-self.event["baseline_count"],
                        percentage_increase=(100*(count-self.event["baseline_count"])/self.event["baseline_count"]
                                             if self.event["baseline_count"] > 0 else None))
        if self.state == "RESOLVED":
            self.state = "NORMAL"
        enough = (len(self.history) >= c.min_samples and
                  self.history[-1][0] - self.history[0][0] >= c.min_history_seconds)
        if self.candidate:
            baseline, mad = self.candidate["baseline"], self.candidate["mad"]
        elif enough:
            values = [v for _, v in self.history]
            baseline = statistics.median(values)
            mad = statistics.median(abs(v - baseline) for v in values)
        else:
            self.history.append((timestamp, count))
            return {"state": "WARMING_UP", "reason": "Collecting baseline history"}
        increase = count - baseline
        percent = 100 * increase / baseline if baseline > 0 else None
        qualifies = (increase >= max(c.min_absolute, c.mad_multiplier * mad)
                     and (percent is None or percent >= c.min_percent))
        evidence = dict(baseline_count=baseline, current_count=count, absolute_increase=increase,
                        percentage_increase=percent, timestamp=timestamp,
                        criteria=c.model_dump(), reason="Sudden crowd increase; organization is not established")
        if qualifies:
            if not self.candidate:
                self.candidate = dict(baseline=baseline, mad=mad, start=timestamp)
            self.state = "CANDIDATE"
            if timestamp - self.candidate["start"] >= c.persistence_seconds:
                self.state = "DETECTED"
                self.event = dict(evidence, state=self.state, start_timestamp=self.candidate["start"])
                self.events.append(self.event.copy())
                self.cooldown_until = timestamp + c.cooldown_seconds
            return dict(evidence, state=self.state)
        self.candidate = None
        self.state = "NORMAL"
        self.history.append((timestamp, count))
        return dict(evidence, state=self.state)
