import os

import pytest
from fastapi.testclient import TestClient

os.environ["GOOGLE_API_KEY"] = "test-mock-key"

from src.api import app
from src.metrics import MetricsCollector, PipelineRunMetric, StageMetric, get_metrics_collector


@pytest.fixture(autouse=True)
def _reset_collector():
    """Reset the global collector singleton for test isolation."""
    import src.api as _api_mod
    import src.metrics as _m

    original = _m._collector
    _m._collector = MetricsCollector()
    yield
    _m._collector = original


@pytest.fixture()
def client():
    return TestClient(app)


@pytest.fixture()
def collector():
    return get_metrics_collector()


def _make_run(**overrides) -> PipelineRunMetric:
    defaults = dict(
        run_id="abc123",
        total_duration_ms=150.0,
        stages=[StageMetric(stage="extract", duration_ms=80.0, success=True)],
        account_type="Futures",
        confidence_score=0.92,
        validation_status="APPROVED",
    )
    defaults.update(overrides)
    return PipelineRunMetric(**defaults)


# --- /api/v1/metrics/summary ---


class TestMetricsSummary:
    def test_empty_state(self, client):
        resp = client.get("/api/v1/metrics/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_runs"] == 0
        assert data["avg_duration_ms"] == 0.0

    def test_with_data(self, client, collector):
        collector.record_run(_make_run())
        resp = client.get("/api/v1/metrics/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_runs"] == 1
        assert data["avg_duration_ms"] == 150.0

    def test_hours_filter(self, client, collector):
        collector.record_run(_make_run(run_id="old1"))
        resp = client.get("/api/v1/metrics/summary?hours=1")
        assert resp.status_code == 200
        assert resp.json()["total_runs"] == 1


# --- /api/v1/metrics/history ---


class TestMetricsHistory:
    def test_empty_state(self, client):
        resp = client.get("/api/v1/metrics/history")
        assert resp.status_code == 200
        data = resp.json()
        assert data["runs"] == []
        assert data["total"] == 0

    def test_with_data(self, client, collector):
        collector.record_run(_make_run())
        resp = client.get("/api/v1/metrics/history")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["runs"]) == 1
        assert data["total"] == 1

    def test_pagination(self, client, collector):
        for i in range(5):
            collector.record_run(_make_run(run_id=f"run{i}"))
        resp = client.get("/api/v1/metrics/history?limit=2&offset=0")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["runs"]) == 2
        assert data["total"] == 5

    def test_offset_beyond_total(self, client, collector):
        collector.record_run(_make_run())
        resp = client.get("/api/v1/metrics/history?offset=100")
        assert resp.status_code == 200
        assert resp.json()["runs"] == []


# --- /api/v1/metrics/stages ---


class TestMetricsStages:
    def test_empty_state(self, client):
        resp = client.get("/api/v1/metrics/stages")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_with_data(self, client, collector):
        collector.record_run(_make_run())
        resp = client.get("/api/v1/metrics/stages")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["stage"] == "extract"
        assert data[0]["count"] == 1


# --- /api/v1/metrics/run/{run_id} ---


class TestMetricsRunDetail:
    def test_found(self, client, collector):
        collector.record_run(_make_run(run_id="xyz789"))
        resp = client.get("/api/v1/metrics/run/xyz789")
        assert resp.status_code == 200
        data = resp.json()
        assert data["run_id"] == "xyz789"

    def test_not_found(self, client):
        resp = client.get("/api/v1/metrics/run/nonexistent")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()


# --- /dashboard ---


class TestDashboard:
    def test_returns_html(self, client):
        resp = client.get("/dashboard")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]
