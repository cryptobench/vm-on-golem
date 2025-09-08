from pathlib import Path
import sys
sys.path.append(str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient
import requestor.api.main as api_main


def test_read_root(tmp_path, monkeypatch):
    monkeypatch.setattr(api_main.config, "db_path", tmp_path / "vms.db")
    with TestClient(api_main.app) as client:
        resp = client.get("/")
        assert resp.status_code == 200
        assert resp.json() == {"message": "Golem Requestor API"}


def test_list_vms_no_db(tmp_path, monkeypatch):
    monkeypatch.setattr(api_main.config, "db_path", tmp_path / "vms.db")
    with TestClient(api_main.app) as client:
        api_main.db_service = None
        resp = client.get("/vms")
        assert resp.status_code == 500


def test_list_vms_returns_vms(tmp_path, monkeypatch):
    monkeypatch.setattr(api_main.config, "db_path", tmp_path / "vms.db")
    with TestClient(api_main.app) as client:
        class Dummy:
            async def list_vms(self):
                return [{"name": "n"}]
        api_main.db_service = Dummy()
        resp = client.get("/vms")
        assert resp.status_code == 200
        assert resp.json() == [{"name": "n"}]
