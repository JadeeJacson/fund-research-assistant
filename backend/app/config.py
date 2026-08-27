from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

import yaml

try:
    from dotenv import dotenv_values
except ImportError:  # pragma: no cover
    dotenv_values = None


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


AI_ENV_KEYS = {
    "FUNDLAB_AI_ENABLED",
    "DEEPSEEK_API_KEY",
    "DEEPSEEK_BASE_URL",
    "DEEPSEEK_MODEL",
}
_ENV_ASSIGNMENT = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=")


def update_local_env(path: Path, updates: dict[str, str | None]) -> None:
    """Atomically update the allow-listed AI settings without exposing their values."""
    if not set(updates).issubset(AI_ENV_KEYS):
        raise ValueError("尝试写入不允许的环境变量")
    path.parent.mkdir(parents=True, exist_ok=True)
    original = path.read_text(encoding="utf-8-sig") if path.exists() else ""
    output: list[str] = []
    handled: set[str] = set()
    for line in original.splitlines():
        match = _ENV_ASSIGNMENT.match(line)
        key = match.group(1) if match else None
        if key not in updates:
            output.append(line)
            continue
        if key in handled:
            continue
        handled.add(key)
        value = updates[key]
        if value is not None:
            output.append(f"{key}={json.dumps(value, ensure_ascii=False)}")
    for key, value in updates.items():
        if key not in handled and value is not None:
            output.append(f"{key}={json.dumps(value, ensure_ascii=False)}")

    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        temporary.write_text("\n".join(output).rstrip("\n") + "\n", encoding="utf-8")
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


@dataclass(frozen=True, slots=True)
class RuleConfig:
    values: dict[str, Any]
    raw: str
    version: str
    sha256: str

    @classmethod
    def load(cls, path: Path) -> RuleConfig:
        raw = path.read_text(encoding="utf-8")
        values = yaml.safe_load(raw)
        if not isinstance(values, dict) or not values.get("version"):
            raise ValueError("decision_rules.yaml 缺少版本")
        buckets = values.get("buckets", {})
        if set(buckets) != {"defense", "core", "satellite"}:
            raise ValueError("规则必须且只能包含三个仓")
        if round(sum(float(item["mid"]) for item in buckets.values()), 8) != 1:
            raise ValueError("三仓中枢之和必须为 100%")
        for item in buckets.values():
            if not 0 <= item["low"] <= item["mid"] <= item["high"] <= 1:
                raise ValueError("仓位区间必须满足 low <= mid <= high")
        return cls(
            values=values,
            raw=raw,
            version=str(values["version"]),
            sha256=hashlib.sha256(raw.encode("utf-8")).hexdigest(),
        )


@dataclass(frozen=True, slots=True)
class Settings:
    project_root: Path
    database_url: str
    upload_dir: Path
    rule_config: RuleConfig
    ai_enabled: bool = False
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-v4-flash"
    market_provider: str = "akshare"
    keep_uploads: bool = True

    @classmethod
    def from_env(cls, project_root: Path | None = None) -> Settings:
        root = (project_root or Path(__file__).resolve().parents[2]).resolve()
        file_values = dotenv_values(root / ".env") if dotenv_values is not None and (root / ".env").exists() else {}

        def value(name: str, default: str = "") -> str:
            configured = os.environ.get(name, file_values.get(name, default))
            return str(configured) if configured is not None else default

        default_db = root / "data" / "private" / "fundlab_v2.sqlite3"
        database_url = value("FUNDLAB_DATABASE_URL", f"sqlite:///{default_db}")
        if database_url.startswith("sqlite:///"):
            database_path = Path(database_url.removeprefix("sqlite:///"))
            if not database_path.is_absolute():
                database_path = root / database_path
            database_path.parent.mkdir(parents=True, exist_ok=True)
            database_url = f"sqlite:///{database_path}"
        upload_dir = Path(value("FUNDLAB_UPLOAD_DIR", "data/private/uploads-v2"))
        if not upload_dir.is_absolute():
            upload_dir = root / upload_dir
        upload_dir.mkdir(parents=True, exist_ok=True)
        rules_path = Path(value("FUNDLAB_RULES_PATH", "config/decision_rules.yaml"))
        if not rules_path.is_absolute():
            rules_path = root / rules_path
        return cls(
            project_root=root,
            database_url=database_url,
            upload_dir=upload_dir,
            rule_config=RuleConfig.load(rules_path),
            ai_enabled=_as_bool(value("FUNDLAB_AI_ENABLED")),
            deepseek_api_key=value("DEEPSEEK_API_KEY").strip(),
            deepseek_base_url=value("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/"),
            deepseek_model=value("DEEPSEEK_MODEL").strip() or "deepseek-v4-flash",
            market_provider=value("FUNDLAB_MARKET_PROVIDER", "akshare").strip().lower(),
            keep_uploads=_as_bool(value("FUNDLAB_KEEP_UPLOADS"), True),
        )
