"""
MetricsCollector untuk mengumpulkan dan menganalisis pipeline performance metrics.
Thread-safe dengan threading.Lock.
"""

import statistics
import threading
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from pydantic import BaseModel, Field


class StageMetric(BaseModel):
    """Metrik untuk satu stage dalam pipeline run."""

    stage: str
    duration_ms: float
    success: bool
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    error_message: Optional[str] = None


class PipelineRunMetric(BaseModel):
    """Metrik untuk satu pipeline run lengkap."""

    run_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    total_duration_ms: float
    stages: list[StageMetric] = Field(default_factory=list)
    account_type: str = ""
    confidence_score: float = 0.0
    validation_status: str = ""
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class StageBreakdown(BaseModel):
    """Ringkasan metrik untuk satu stage."""

    stage: str
    count: int
    avg_duration_ms: float
    success_rate: float
    error_count: int


class MetricsSummary(BaseModel):
    """Ringkasan agregat dari semua pipeline runs."""

    total_runs: int = 0
    successful_runs: int = 0
    failed_runs: int = 0
    success_rate: float = 0.0
    avg_duration_ms: float = 0.0
    min_duration_ms: float = 0.0
    max_duration_ms: float = 0.0
    p50_duration_ms: float = 0.0
    p95_duration_ms: float = 0.0
    p99_duration_ms: float = 0.0
    avg_confidence: float = 0.0
    stage_breakdown: list[StageBreakdown] = Field(default_factory=list)
    period_start: str = ""
    period_end: str = ""


class MetricsCollector:
    """Thread-safe metrics collector untuk pipeline performance monitoring."""

    def __init__(self, max_records: int = 10_000) -> None:
        self._records: list[PipelineRunMetric] = []
        self._lock = threading.Lock()
        self._max_records = max_records

    def record_run(self, metric: PipelineRunMetric) -> None:
        """Record satu pipeline run metric. Thread-safe."""
        with self._lock:
            self._records.append(metric)
            if len(self._records) > self._max_records:
                self._records = self._records[-self._max_records:]

    def get_history(
        self, limit: int = 50, offset: int = 0
    ) -> list[PipelineRunMetric]:
        """Ambil history pipeline runs dengan pagination. Terbaru di atas."""
        with self._lock:
            reversed_records = list(reversed(self._records))
            return reversed_records[offset : offset + limit]

    def get_summary(self, hours: Optional[int] = None) -> MetricsSummary:
        """Hitung summary metrics. Filter by hours jika ditentukan."""
        with self._lock:
            records = self._filter_by_hours(hours)

            if not records:
                return MetricsSummary()

            durations = [r.total_duration_ms for r in records]
            confidences = [r.confidence_score for r in records]

            successful = sum(1 for r in records if r.validation_status != "REJECTED")
            failed = len(records) - successful

            stage_stats: dict[str, dict] = {}
            for r in records:
                for s in r.stages:
                    if s.stage not in stage_stats:
                        stage_stats[s.stage] = {
                            "durations": [],
                            "successes": 0,
                            "errors": 0,
                        }
                    stage_stats[s.stage]["durations"].append(s.duration_ms)
                    if s.success:
                        stage_stats[s.stage]["successes"] += 1
                    else:
                        stage_stats[s.stage]["errors"] += 1

            stage_breakdown = []
            for stage_name, stats in stage_stats.items():
                count = len(stats["durations"])
                stage_breakdown.append(
                    StageBreakdown(
                        stage=stage_name,
                        count=count,
                        avg_duration_ms=statistics.mean(stats["durations"]),
                        success_rate=stats["successes"] / count if count > 0 else 0.0,
                        error_count=stats["errors"],
                    )
                )

            timestamps = [r.timestamp for r in records]

            return MetricsSummary(
                total_runs=len(records),
                successful_runs=successful,
                failed_runs=failed,
                success_rate=successful / len(records) if records else 0.0,
                avg_duration_ms=statistics.mean(durations),
                min_duration_ms=min(durations),
                max_duration_ms=max(durations),
                p50_duration_ms=self._percentile(durations, 50),
                p95_duration_ms=self._percentile(durations, 95),
                p99_duration_ms=self._percentile(durations, 99),
                avg_confidence=statistics.mean(confidences) if confidences else 0.0,
                stage_breakdown=stage_breakdown,
                period_start=min(timestamps) if timestamps else "",
                period_end=max(timestamps) if timestamps else "",
            )

    def get_stage_breakdown(self, hours: Optional[int] = None) -> list[StageBreakdown]:
        """Ambil breakdown per stage."""
        with self._lock:
            records = self._filter_by_hours(hours)

            stage_stats: dict[str, dict] = {}
            for r in records:
                for s in r.stages:
                    if s.stage not in stage_stats:
                        stage_stats[s.stage] = {
                            "durations": [],
                            "successes": 0,
                            "errors": 0,
                        }
                    stage_stats[s.stage]["durations"].append(s.duration_ms)
                    if s.success:
                        stage_stats[s.stage]["successes"] += 1
                    else:
                        stage_stats[s.stage]["errors"] += 1

            result = []
            for stage_name, stats in stage_stats.items():
                count = len(stats["durations"])
                result.append(
                    StageBreakdown(
                        stage=stage_name,
                        count=count,
                        avg_duration_ms=statistics.mean(stats["durations"]),
                        success_rate=stats["successes"] / count if count > 0 else 0.0,
                        error_count=stats["errors"],
                    )
                )
            return result

    def clear_old_records(self, days: int = 30) -> int:
        """Hapus records lebih lama dari days. Return jumlah yang dihapus."""
        with self._lock:
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)
            cutoff_iso = cutoff.isoformat()
            original_count = len(self._records)
            self._records = [
                r for r in self._records if r.timestamp >= cutoff_iso
            ]
            return original_count - len(self._records)

    def get_all_records(self) -> list[PipelineRunMetric]:
        """Ambil semua records (copy)."""
        with self._lock:
            return list(self._records)

    def _filter_by_hours(self, hours: Optional[int]) -> list[PipelineRunMetric]:
        """Filter records by hours. Must be called with lock held."""
        if hours is None:
            return list(self._records)

        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        cutoff_iso = cutoff.isoformat()
        return [r for r in self._records if r.timestamp >= cutoff_iso]

    @staticmethod
    def _percentile(data: list[float], pct: float) -> float:
        """Hitung percentile dari data list."""
        if not data:
            return 0.0
        sorted_data = sorted(data)
        k = (len(sorted_data) - 1) * (pct / 100)
        f = int(k)
        c = f + 1
        if c >= len(sorted_data):
            return sorted_data[f]
        return sorted_data[f] + (k - f) * (sorted_data[c] - sorted_data[f])


_collector: Optional[MetricsCollector] = None
_collector_lock = threading.Lock()


def get_metrics_collector(max_records: int = 10_000) -> MetricsCollector:
    """Global singleton MetricsCollector. Thread-safe initialization."""
    global _collector
    if _collector is None:
        with _collector_lock:
            if _collector is None:
                _collector = MetricsCollector(max_records=max_records)
    return _collector
