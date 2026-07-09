import io
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

os.environ["GOOGLE_API_KEY"] = "test-mock-key"

from src.api import app, ALLOWED_EXTENSIONS, ACCOUNT_TYPES

client = TestClient(app)


class TestHealth:
    def test_health_returns_ok(self):
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["service"] == "multi-agent-onboarding"


class TestValidate:
    def test_missing_file_returns_422(self):
        resp = client.post("/api/v1/validate", data={"account_type": "Futures"})
        assert resp.status_code == 422

    def test_invalid_account_type_returns_400(self):
        resp = client.post(
            "/api/v1/validate",
            data={"account_type": "InvalidType"},
            files={"file": ("test.jpg", b"fake-image-data", "image/jpeg")},
        )
        assert resp.status_code == 400
        assert "Account type tidak valid" in resp.json()["detail"]

    def test_empty_file_returns_400(self):
        resp = client.post(
            "/api/v1/validate",
            data={"account_type": "Futures"},
            files={"file": ("test.jpg", b"", "image/jpeg")},
        )
        assert resp.status_code == 400
        assert "File kosong" in resp.json()["detail"]

    def test_invalid_extension_returns_400(self):
        resp = client.post(
            "/api/v1/validate",
            data={"account_type": "Futures"},
            files={"file": ("test.txt", b"not-an-image", "text/plain")},
        )
        assert resp.status_code == 400
        assert "Format file tidak didukung" in resp.json()["detail"]


class TestListCustomers:
    def test_returns_list(self):
        resp = client.get("/api/v1/customers")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


class TestListAuditLogs:
    def test_returns_list(self):
        resp = client.get("/api/v1/audit-logs")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


class TestAllowedExtensions:
    def test_jpg_allowed(self):
        assert ".jpg" in ALLOWED_EXTENSIONS

    def test_png_allowed(self):
        assert ".png" in ALLOWED_EXTENSIONS

    def test_txt_not_allowed(self):
        assert ".txt" not in ALLOWED_EXTENSIONS


class TestAccountTypes:
    def test_futures_included(self):
        assert "Futures" in ACCOUNT_TYPES

    def test_stocks_included(self):
        assert "Stocks" in ACCOUNT_TYPES

    def test_invalid_excluded(self):
        assert "InvalidType" not in ACCOUNT_TYPES


class TestRouteExistence:
    def test_route_exists(self):
        paths = {r.path for r in app.routes if hasattr(r, "path")}
        assert "/api/v1/health" in paths
        assert "/api/v1/validate" in paths
        assert "/api/v1/customers" in paths
        assert "/api/v1/audit-logs" in paths
