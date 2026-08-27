import base64
import shutil
from datetime import date
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from app.providers import FixtureProvider


def build_client(tmp_path):
    (tmp_path / "config").mkdir()
    shutil.copyfile(
        Path(__file__).parents[2] / "config" / "decision_rules.yaml",
        tmp_path / "config" / "decision_rules.yaml",
    )
    app = create_app(
        database_url=f"sqlite:///{tmp_path / 'test.sqlite3'}",
        project_root=tmp_path,
        provider=FixtureProvider(),
    )
    return TestClient(app)


def complete_snapshot_payload():
    return {
        "as_of_date": date.today().isoformat(),
        "completeness": "complete",
        "source": "manual",
        "items": [
            {"fund_code": "000009", "fund_name": "易方达天天理财货币A", "amount": 400, "bucket": "defense"},
            {"fund_code": "019028", "fund_name": "广发添福30天持有期债券C", "amount": 350, "bucket": "core"},
            {"fund_code": "017470", "fund_name": "嘉实上证科创板芯片ETF联接C", "amount": 250, "bucket": "satellite"},
        ],
    }


def test_first_run_snapshot_review_decision_and_export(tmp_path):
    client = build_client(tmp_path)
    health = client.get("/api/v2/health")
    assert health.status_code == 200
    assert health.json()["rule_version"] == "v2.1.2"
    assert client.get("/api/v1/health").status_code == 404
    assert client.get("/api/v2/portfolio").json()["capital_budget"] == 0

    partial = complete_snapshot_payload()
    partial["completeness"] = "partial"
    assert client.post("/api/v2/portfolio/snapshots", json=partial).status_code == 201
    assert client.post("/api/v2/reviews").status_code == 409

    snapshot = client.post("/api/v2/portfolio/snapshots", json=complete_snapshot_payload())
    assert snapshot.status_code == 201
    assert snapshot.json()["total_market_value"] == 1000
    started = client.post("/api/v2/reviews")
    assert started.status_code == 202
    run = client.get(f"/api/v2/reviews/{started.json()['run_id']}").json()
    assert run["status"] in {"completed", "partial"}
    assert run["progress"] == 100
    assert run["rule_version"] == "v2.1.2"
    assert set(run["bucket_summary"]) == {"defense", "core", "satellite"}

    if run["items"]:
        decision = client.post(
            f"/api/v2/review-items/{run['items'][0]['id']}/decision",
            json={"user_choice": "defer", "note": "下次再看"},
        )
        assert decision.status_code == 200
        assert decision.json()["status"] == "deferred"

    exported = client.get("/api/v2/exports/full")
    assert exported.status_code == 200
    assert exported.json()["portfolio"]["latest_snapshot"]["id"] == snapshot.json()["id"]
    assert client.post("/api/v2/settings/ai/test").json()["status"] == "disabled"
    ai_health = client.get("/api/v2/data-health").json()
    assert ai_health["ai"] == "disabled"
    assert "FUNDLAB_AI_ENABLED=true" in ai_health["ai_config"]["missing"]


def test_ai_health_reports_configured_without_exposing_key(tmp_path, monkeypatch):
    monkeypatch.setenv("FUNDLAB_AI_ENABLED", "true")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-secret-never-returned")
    monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-v4-flash")
    client = build_client(tmp_path)
    health = client.get("/api/v2/data-health").json()
    assert health["ai"] == "configured"
    assert health["ai_config"]["key_configured"] is True
    assert health["ai_config"]["model"] == "deepseek-v4-flash"
    assert "test-secret-never-returned" not in str(health)


def test_ai_explanation_is_user_triggered_persisted_and_cached(tmp_path, monkeypatch):
    monkeypatch.setenv("FUNDLAB_AI_ENABLED", "true")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-secret-never-returned")
    monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-v4-flash")
    calls = []

    async def fake_explain(settings, review, evidence):
        calls.append({"review": review, "evidence": evidence})
        return {
            "status": "ok",
            "summary": "本次只解释确定性结果。",
            "supporting_points": [{"text": "仓位偏离需要复核", "evidence_ids": []}],
            "counterpoints": [],
            "unknowns": ["没有文档证据"],
        }

    monkeypatch.setattr("app.main.explain_review", fake_explain)
    client = build_client(tmp_path)
    assert client.post("/api/v2/portfolio/snapshots", json=complete_snapshot_payload()).status_code == 201
    run_id = client.post("/api/v2/reviews").json()["run_id"]
    assert client.get(f"/api/v2/reviews/{run_id}/explanation").json() is None

    first = client.post(f"/api/v2/reviews/{run_id}/explain")
    second = client.post(f"/api/v2/reviews/{run_id}/explain")

    assert first.status_code == second.status_code == 200
    assert first.json()["summary"] == "本次只解释确定性结果。"
    assert second.json()["cached"] is True
    assert len(calls) == 1
    assert "amount" not in str(calls[0]["review"])
    assert "target_delta" not in str(calls[0]["review"])
    assert client.get(f"/api/v2/reviews/{run_id}/explanation").json()["status"] == "ok"


def test_ai_settings_can_be_saved_without_returning_the_key(tmp_path):
    client = build_client(tmp_path)
    initial = client.get("/api/v2/settings/ai")
    assert initial.status_code == 200
    assert initial.json()["key_configured"] is False

    saved = client.put(
        "/api/v2/settings/ai",
        json={
            "enabled": True,
            "api_key": "test-secret-never-returned",
            "base_url": "https://api.deepseek.com",
            "model": "deepseek-v4-flash",
        },
    )
    assert saved.status_code == 200
    assert saved.json()["status"] == "configured"
    assert saved.json()["key_configured"] is True
    assert saved.json()["message"] == "AI 配置已保存并即时生效"
    assert "test-secret-never-returned" not in saved.text
    assert "test-secret-never-returned" in (tmp_path / ".env").read_text(encoding="utf-8")

    preserved = client.put(
        "/api/v2/settings/ai",
        json={
            "enabled": True,
            "base_url": "https://api.deepseek.com",
            "model": "deepseek-v4-pro",
        },
    )
    assert preserved.status_code == 200
    assert preserved.json()["key_configured"] is True
    assert preserved.json()["model"] == "deepseek-v4-pro"
    assert "test-secret-never-returned" not in client.get("/api/v2/settings/ai").text

    cleared = client.put(
        "/api/v2/settings/ai",
        json={
            "enabled": False,
            "clear_api_key": True,
            "base_url": "https://api.deepseek.com",
            "model": "deepseek-v4-pro",
        },
    )
    assert cleared.status_code == 200
    assert cleared.json()["key_configured"] is False
    assert "test-secret-never-returned" not in (tmp_path / ".env").read_text(encoding="utf-8")


def test_ai_settings_reject_unsafe_url_and_environment_override(tmp_path, monkeypatch):
    client = build_client(tmp_path)
    unsafe = client.put(
        "/api/v2/settings/ai",
        json={"enabled": True, "api_key": "secret", "base_url": "http://example.com", "model": "deepseek-v4-flash"},
    )
    assert unsafe.status_code == 422
    assert "secret" not in unsafe.text

    ambiguous = client.put(
        "/api/v2/settings/ai",
        json={"enabled": True, "api_key": "another-secret", "clear_api_key": True, "base_url": "https://api.deepseek.com", "model": "deepseek-v4-flash"},
    )
    assert ambiguous.status_code == 422
    assert "another-secret" not in ambiguous.text

    monkeypatch.setenv("DEEPSEEK_API_KEY", "managed-outside-app")
    overridden = client.put(
        "/api/v2/settings/ai",
        json={"enabled": True, "api_key": "new-secret", "base_url": "https://api.deepseek.com", "model": "deepseek-v4-flash"},
    )
    assert overridden.status_code == 409
    assert "DEEPSEEK_API_KEY" in overridden.json()["detail"]


def test_verified_manual_hard_risk_does_not_require_loss(tmp_path):
    client = build_client(tmp_path)
    assert client.post("/api/v2/portfolio/snapshots", json=complete_snapshot_payload()).status_code == 201
    evidence = client.post(
        "/api/v2/evidence/manual",
        json={
            "fund_code": "019028",
            "evidence_kind": "announcement",
            "title": "基金合同终止公告",
            "source_url": "https://example.com/official.pdf",
            "source_level": "S",
            "published_at": date.today().isoformat(),
            "event_type": "contract_termination",
            "verified": True,
        },
    )
    assert evidence.status_code == 201
    started = client.post("/api/v2/reviews").json()
    run = client.get(f"/api/v2/reviews/{started['run_id']}").json()
    hard = [item for item in run["items"] if item["reason_type"] == "hard_risk"]
    assert hard and hard[0]["proposed_action"] == "exit_review"


def test_bucket_override_and_input_validation(tmp_path):
    client = build_client(tmp_path)
    assert client.post("/api/v2/funds", json={"code": "000001", "name": "华夏成长混合A"}).status_code == 201
    override = client.put("/api/v2/funds/000001/bucket", json={"bucket": "core", "note": "长期配置"})
    assert override.status_code == 200
    duplicate = complete_snapshot_payload()
    duplicate["items"].append(duplicate["items"][0])
    assert client.post("/api/v2/portfolio/snapshots", json=duplicate).status_code == 422


def test_fund_detail_exposes_percentage_chart_and_risk_metrics(tmp_path):
    client = build_client(tmp_path)
    refreshed = client.post("/api/v2/funds/017470/refresh")

    assert refreshed.status_code == 200
    detail = refreshed.json()
    assert detail["performance"]["observations"] == 253
    assert detail["performance"]["return_1m"] is not None
    assert detail["performance"]["return_3m"] is not None
    assert detail["performance"]["return_1y"] is not None
    assert detail["performance"]["volatility"] is not None
    assert detail["performance"]["max_drawdown"] <= 0
    assert detail["performance_chart"][0]["cumulative_return"] == 0
    assert all(point["drawdown"] <= 0 for point in detail["performance_chart"])


def test_optional_personal_profit_and_bucket_summary_are_persisted(tmp_path):
    client = build_client(tmp_path)
    payload = complete_snapshot_payload()
    payload["items"][0]["displayed_profit"] = -18.6
    created = client.post("/api/v2/portfolio/snapshots", json=payload)
    assert created.status_code == 201
    assert created.json()["items"][0]["displayed_profit"] == -18.6
    portfolio = client.get("/api/v2/portfolio").json()
    assert portfolio["current_bucket_summary"]["defense"]["amount"] == 400
    assert portfolio["current_bucket_summary"]["core"]["weight"] == 0.35


def test_ocr_profit_flows_through_draft_and_confirmation(tmp_path):
    client = build_client(tmp_path)
    client.app.state.ocr.extract = lambda _: (
        "全部持有\n017470\n持有金额 250.00元\n持有收益 -12.30元",
        [0.98],
        [],
    )
    tiny_png = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAFklEQVR4nGP8//8/AwMDEwMDAwMDAwAkBgMB/DXemwAAAABJRU5ErkJggg=="
    )
    uploaded = client.post("/api/v2/imports", files={"image": ("profit.png", tiny_png, "image/png")}).json()
    processed = client.post(f"/api/v2/imports/{uploaded['id']}/process")
    assert processed.status_code == 200
    assert processed.json()["items"][0]["displayed_profit"] == -12.3
    confirmed = client.post(
        f"/api/v2/imports/{uploaded['id']}/confirm",
        json={
            "as_of_date": date.today().isoformat(),
            "completeness": "complete",
            "items": [{"fund_code": "017470", "fund_name": "测试基金", "amount": 250, "displayed_profit": -12.3, "bucket": "satellite"}],
        },
    )
    assert confirmed.status_code == 201
    assert confirmed.json()["items"][0]["displayed_profit"] == -12.3


def test_name_only_ocr_is_resolved_and_automatically_assigned_to_bucket(tmp_path):
    client = build_client(tmp_path)
    client.app.state.ocr.extract = lambda _: (
        "全部持有\n嘉实上证科创板芯片ETF联接C\n基金\n63.64\n0.00\n-13.72\n-13.72\n占比 2.44%\n-17.73%",
        [0.97],
        [],
    )
    tiny_png = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAFklEQVR4nGP8//8/AwMDEwMDAwMDAwAkBgMB/DXemwAAAABJRU5ErkJggg=="
    )
    uploaded = client.post(
        "/api/v2/imports",
        files={"image": ("name-only.png", tiny_png, "image/png")},
    ).json()
    processed = client.post(f"/api/v2/imports/{uploaded['id']}/process")

    assert processed.status_code == 200
    item = processed.json()["items"][0]
    assert item["fund_code"] == "017470"
    assert item["amount"] == 63.64
    assert item["displayed_profit"] == -13.72
    assert item["bucket"] == "satellite"
    assert "自动归入卫星进攻仓" in item["issues"]


def test_snapshot_idempotency_key_replays_same_response(tmp_path):
    client = build_client(tmp_path)
    headers = {"Idempotency-Key": "snapshot-test-1"}
    first = client.post("/api/v2/portfolio/snapshots", json=complete_snapshot_payload(), headers=headers)
    second = client.post("/api/v2/portfolio/snapshots", json=complete_snapshot_payload(), headers=headers)
    assert first.status_code == second.status_code == 201
    assert first.json()["id"] == second.json()["id"]
    changed = complete_snapshot_payload()
    changed["items"][0]["amount"] = 401
    assert client.post("/api/v2/portfolio/snapshots", json=changed, headers=headers).status_code == 409


def test_import_rejects_non_image_and_draft_does_not_enable_review(tmp_path):
    client = build_client(tmp_path)
    assert client.post(
        "/api/v2/imports", files={"image": ("bad.txt", b"not image", "text/plain")}
    ).status_code == 415
    tiny_png = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAFklEQVR4nGP8//8/AwMDEwMDAwMDAwAkBgMB/DXemwAAAABJRU5ErkJggg=="
    )
    uploaded = client.post(
        "/api/v2/imports", files={"image": ("holding.png", tiny_png, "image/png")}
    )
    assert uploaded.status_code == 201
    assert uploaded.json()["status"] == "uploaded"
    assert client.post("/api/v2/reviews").status_code == 409


def test_discovery_requires_snapshot_and_persists_manual_run(tmp_path):
    client = build_client(tmp_path)
    assert client.post("/api/v2/discoveries").status_code == 409
    assert client.post("/api/v2/portfolio/snapshots", json=complete_snapshot_payload()).status_code == 201

    started = client.post("/api/v2/discoveries")
    latest = client.get("/api/v2/discoveries/latest")

    assert started.status_code == 202
    assert latest.status_code == 200
    assert latest.json()["id"] == started.json()["run_id"]
    assert latest.json()["status"] in {"completed", "partial"}
    assert latest.json()["progress"] == 100
    assert isinstance(latest.json()["results"], list)


def test_bucket_deviation_is_display_only_and_never_enters_review(tmp_path):
    client = build_client(tmp_path)
    payload = complete_snapshot_payload()
    payload["items"][0]["amount"] = 200
    payload["items"][1]["amount"] = 550
    assert client.post("/api/v2/portfolio/snapshots", json=payload).status_code == 201
    run_id = client.post("/api/v2/reviews").json()["run_id"]
    run = client.get(f"/api/v2/reviews/{run_id}").json()

    assert run["bucket_summary"]["defense"]["in_band"] is False
    assert run["bucket_summary"]["core"]["in_band"] is False
    assert all(item["reason_type"] != "band_breach" for item in run["items"])
    assert all(item.get("reason_type") != "band_breach" for item in run["headlines"])
