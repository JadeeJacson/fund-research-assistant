import base64
from datetime import UTC, date, datetime

from fastapi.testclient import TestClient

from app.main import create_app


def build_client(tmp_path):
    app = create_app(
        database_url=f"sqlite:///{tmp_path / 'test.sqlite3'}",
        project_root=tmp_path,
    )
    app.state.provider.mode = "demo"
    return TestClient(app)


def test_candidate_report_holding_trigger_flow(tmp_path):
    client = build_client(tmp_path)
    assert client.get("/api/v1/health").status_code == 200

    created = client.post("/api/v1/candidates", json={"fund_code": "017470"})
    assert created.status_code == 201
    candidate = created.json()

    refreshed = client.post(f"/api/v1/candidates/{candidate['id']}/refresh")
    assert refreshed.status_code == 200
    assert "演示" in refreshed.json()["data_source"]

    holding = client.post(
        "/api/v1/holdings",
        json={
            "fund_code": "017470",
            "fund_name": "嘉实上证科创板芯片ETF联接C",
            "amount": 100,
            "snapshot_date": date.today().isoformat(),
        },
    )
    assert holding.status_code == 201

    report = client.post(
        "/api/v1/reports",
        json={"candidate_id": candidate["id"], "horizon": "short"},
    )
    assert report.status_code == 200
    assert report.json()["decision"]["state"]
    assert report.json()["horizon"] == "short"

    trigger = client.post(
        "/api/v1/triggers",
        json={
            "candidate_id": candidate["id"],
            "metric": "latest_nav",
            "operator": ">",
            "threshold": 0,
        },
    )
    assert trigger.status_code == 201
    checked = client.post("/api/v1/triggers/check")
    assert checked.status_code == 200
    assert checked.json()[0]["last_matched"] is True


def test_transaction_deduplication(tmp_path):
    client = build_client(tmp_path)
    payload = {
        "fund_code": "006985",
        "fund_name": "兴全恒裕债券A",
        "action": "buy",
        "amount": 1000,
        "trade_time": datetime.now(UTC).isoformat(),
    }
    assert client.post("/api/v1/transactions", json=payload).status_code == 201
    assert client.post("/api/v1/transactions", json=payload).status_code == 409


def test_import_requires_supported_image(tmp_path):
    client = build_client(tmp_path)
    response = client.post(
        "/api/v1/imports",
        files={"image": ("bad.txt", b"not an image", "text/plain")},
    )
    assert response.status_code == 415


def test_manual_review_can_confirm_an_ocr_draft(tmp_path):
    client = build_client(tmp_path)
    tiny_png = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAFklEQVR4nGP8//8/AwMDEwMDAwMDAwAkBgMB/DXemwAAAABJRU5ErkJggg=="
    )
    uploaded = client.post(
        "/api/v1/imports",
        files={"image": ("candidate.png", tiny_png, "image/png")},
    )
    assert uploaded.status_code == 201
    batch = uploaded.json()
    draft_id = batch["items"][0]["id"]
    corrected = client.put(
        f"/api/v1/import-items/{draft_id}",
        json={
            "kind": "candidate",
            "fund_code": "020972",
            "fund_name": "易方达机器人ETF联接A",
            "action": "",
            "amount": None,
            "shares": None,
            "event_time": None,
        },
    )
    assert corrected.status_code == 200
    confirmed = client.post(f"/api/v1/imports/{batch['id']}/confirm")
    assert confirmed.status_code == 200
    assert confirmed.json()["status"] == "confirmed"
    assert client.get("/api/v1/candidates").json()[0]["fund_code"] == "020972"
