import threading
from datetime import datetime, timedelta, timezone

import pytest

from src.metrics import (
    MetricsCollector,
    MetricsSummary,
    PipelineRunMetric,
    StageMetric,
    get_metrics_collector,
)


def _make_run(
    stages: list[StageMetric] | None = None,
    total_duration_ms: float = 100.0,
    validation_status: str = "PROCEED",
    confidence_score: float = 0.8,
    account_type: str = "Stocks",
    ts: str | None = None,
) -> PipelineRunMetric:
    """Helper untuk membuat PipelineRunMetric."""
    if stages is None:
        stages = [
            StageMetric(stage="extract", duration_ms=50.0, success=True),
            StageMetric(stage="validate", duration_ms=50.0, success=True),
        ]
    return PipelineRunMetric(
        total_duration_ms=total_duration_ms,
        stages=stages,
        account_type=account_type,
        confidence_score=confidence_score,
        validation_status=validation_status,
        timestamp=ts or datetime.now(timezone.utc).isoformat(),
    )


class TestRecordRun:
    def test_record_run(self):
        collector = MetricsCollector()
        metric = _make_run()
        collector.record_run(metric)
        records = collector.get_all_records()
        assert len(records) == 1
        assert records[0].run_id == metric.run_id

    def test_record_multiple_runs(self):
        collector = MetricsCollector()
        for _ in range(5):
            collector.record_run(_make_run())
        assert len(collector.get_all_records()) == 5


class TestMaxRecords:
    def test_max_records_limit(self):
        collector = MetricsCollector(max_records=3)
        for i in range(5):
            collector.record_run(_make_run(total_duration_ms=float(i * 100)))
        records = collector.get_all_records()
        assert len(records) == 3
        assert records[0].total_duration_ms == 200.0
        assert records[-1].total_duration_ms == 400.0


class TestGetSummary:
    def test_get_summary_empty(self):
        collector = MetricsCollector()
        summary = collector.get_summary()
        assert summary.total_runs == 0
        assert summary.successful_runs == 0
        assert summary.failed_runs == 0
        assert summary.success_rate == 0.0
        assert summary.avg_duration_ms == 0.0

    def test_get_summary_with_data(self):
        collector = MetricsCollector()
        collector.record_run(
            _make_run(total_duration_ms=100.0, confidence_score=0.9, validation_status="PROCEED")
        )
        collector.record_run(
            _make_run(total_duration_ms=200.0, confidence_score=0.6, validation_status="PROCEED")
        )
        collector.record_run(
            _make_run(total_duration_ms=150.0, confidence_score=0.4, validation_status="REJECTED")
        )

        summary = collector.get_summary()
        assert summary.total_runs == 3
        assert summary.successful_runs == 2
        assert summary.failed_runs == 1
        assert summary.success_rate == pytest.approx(2 / 3)
        assert summary.avg_duration_ms == pytest.approx(150.0)
        assert summary.min_duration_ms == 100.0
        assert summary.max_duration_ms == 200.0
        assert summary.avg_confidence == pytest.approx(0.6333, abs=0.01)

    def test_get_summary_with_hours_filter(self):
        collector = MetricsCollector()
        old_ts = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()
        recent_ts = datetime.now(timezone.utc).isoformat()
        collector.record_run(_make_run(total_duration_ms=100.0, ts=old_ts))
        collector.record_run(_make_run(total_duration_ms=200.0, ts=recent_ts))

        summary = collector.get_summary(hours=1)
        assert summary.total_runs == 1
        assert summary.avg_duration_ms == 200.0


class TestGetHistory:
    def test_get_history_pagination(self):
        collector = MetricsCollector()
        for i in range(10):
            collector.record_run(_make_run(total_duration_ms=float(i)))

        page1 = collector.get_history(limit=3, offset=0)
        page2 = collector.get_history(limit=3, offset=3)
        assert len(page1) == 3
        assert len(page2) == 3
        assert page1[0].total_duration_ms != page2[0].total_duration_ms

    def test_get_history_empty(self):
        collector = MetricsCollector()
        history = collector.get_history()
        assert history == []

    def test_get_history_order(self):
        collector = MetricsCollector()
        collector.record_run(_make_run(total_duration_ms=100.0))
        collector.record_run(_make_run(total_duration_ms=200.0))
        history = collector.get_history()
        assert history[0].total_duration_ms == 200.0
        assert history[1].total_duration_ms == 100.0


class TestClearOldRecords:
    def test_clear_old_records(self):
        collector = MetricsCollector()
        old_ts = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()
        recent_ts = datetime.now(timezone.utc).isoformat()
        collector.record_run(_make_run(ts=old_ts))
        collector.record_run(_make_run(ts=recent_ts))

        removed = collector.clear_old_records(days=30)
        assert removed == 1
        assert len(collector.get_all_records()) == 1


class TestStageBreakdown:
    def test_stage_breakdown(self):
        collector = MetricsCollector()
        stages = [
            StageMetric(stage="extract", duration_ms=80.0, success=True),
            StageMetric(stage="validate", duration_ms=50.0, success=True),
        ]
        collector.record_run(_make_run(stages=stages, total_duration_ms=130.0))

        stages2 = [
            StageMetric(stage="extract", duration_ms=120.0, success=True),
            StageMetric(stage="validate", duration_ms=30.0, success=False, error_message="fail"),
        ]
        collector.record_run(_make_run(stages=stages2, total_duration_ms=150.0))

        breakdown = collector.get_stage_breakdown()
        assert len(breakdown) == 2
        extract = next(b for b in breakdown if b.stage == "extract")
        assert extract.count == 2
        assert extract.avg_duration_ms == pytest.approx(100.0)
        assert extract.success_rate == 1.0

        validate = next(b for b in breakdown if b.stage == "validate")
        assert validate.count == 2
        assert validate.error_count == 1
        assert validate.success_rate == 0.5


class TestSingleton:
    def test_singleton(self):
        a = get_metrics_collector()
        b = get_metrics_collector()
        assert a is b

    def test_singleton_recorded_data_persists(self):
        collector = get_metrics_collector()
        before = len(collector.get_all_records())
        collector.record_run(_make_run())
        after = len(collector.get_all_records())
        assert after == before + 1


class TestThreadSafety:
    def test_concurrent_record_run(self):
        collector = MetricsCollector()
        errors: list[Exception] = []

        def worker():
            try:
                for _ in range(100):
                    collector.record_run(_make_run())
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        assert len(collector.get_all_records()) == 400
