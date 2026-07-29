from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - 正式依赖包含 python-dotenv
    load_dotenv = None


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True, slots=True)
class Settings:
    project_root: Path
    database_url: str
    upload_dir: Path
    risk_tolerance: float = 0.10
    ai_enabled: bool = False
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = ""
    market_provider: str = "auto"
    keep_uploads: bool = True

    @classmethod
    def from_env(cls, project_root: Path | None = None) -> "Settings":
        root = (project_root or Path(__file__).resolve().parents[2]).resolve()
        if load_dotenv is not None:
            load_dotenv(root / ".env", override=False)
        default_db = root / "data" / "private" / "fundlab_v1.sqlite3"
        database_url = os.getenv("FUNDLAB_V1_DATABASE_URL", f"sqlite:///{default_db}")
        if database_url.startswith("sqlite:///"):
            database_path = Path(database_url.removeprefix("sqlite:///"))
            if not database_path.is_absolute():
                database_path = root / database_path
            database_url = f"sqlite:///{database_path}"
        upload_dir = Path(os.getenv("FUNDLAB_V1_UPLOAD_DIR", "data/private/uploads"))
        if not upload_dir.is_absolute():
            upload_dir = root / upload_dir
        upload_dir.mkdir(parents=True, exist_ok=True)
        if database_url.startswith("sqlite:///"):
            Path(database_url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
        return cls(
            project_root=root,
            database_url=database_url,
            upload_dir=upload_dir,
            risk_tolerance=float(os.getenv("FUNDLAB_RISK_TOLERANCE", "0.10")),
            ai_enabled=_as_bool(os.getenv("FUNDLAB_AI_ENABLED")),
            deepseek_api_key=os.getenv("DEEPSEEK_API_KEY", "").strip(),
            deepseek_base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip(
                "/"
            ),
            deepseek_model=os.getenv("DEEPSEEK_MODEL", "").strip(),
            market_provider=os.getenv("FUNDLAB_MARKET_PROVIDER", "auto").strip().lower(),
            keep_uploads=_as_bool(os.getenv("FUNDLAB_KEEP_UPLOADS"), True),
        )
