"""集中配置。

用户通常只需要修改项目根目录下的 ``.env``，不要在业务代码中硬编码
Token、模型名称、数据库路径或风险阈值。
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:  # 允许在最小测试环境中不安装 python-dotenv。
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - 正式依赖安装后不会走这里
    load_dotenv = None


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True, slots=True)
class Settings:
    """应用运行参数。所有可由用户调整的设置集中在这里。"""

    project_root: Path
    data_dir: Path
    database_path: Path
    risk_tolerance: float = 0.10
    risk_free_rate: float = 0.0
    ai_enabled: bool = False
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-v4-flash"
    deepseek_thinking: bool = False
    deepseek_timeout_seconds: float = 60.0
    deepseek_max_retries: int = 2
    deepseek_max_tokens: int = 2200
    deepseek_daily_budget_usd: float = 0.0
    deepseek_input_price_per_million_usd: float = 0.0
    deepseek_output_price_per_million_usd: float = 0.0

    @classmethod
    def from_env(cls, project_root: Path | None = None) -> Settings:
        root = (project_root or Path.cwd()).resolve()
        if load_dotenv is not None:
            load_dotenv(root / ".env", override=False)

        data_raw = Path(os.getenv("FUNDLAB_DATA_DIR", "data"))
        data_dir = data_raw if data_raw.is_absolute() else root / data_raw
        database_raw = Path(os.getenv("FUNDLAB_DATABASE_PATH", "data/private/fundlab.sqlite3"))
        database_path = database_raw if database_raw.is_absolute() else root / database_raw

        settings = cls(
            project_root=root,
            data_dir=data_dir,
            database_path=database_path,
            risk_tolerance=float(os.getenv("FUNDLAB_RISK_TOLERANCE", "0.10")),
            risk_free_rate=float(os.getenv("FUNDLAB_RISK_FREE_RATE", "0")),
            ai_enabled=_as_bool(os.getenv("FUNDLAB_AI_ENABLED")),
            deepseek_api_key=os.getenv("DEEPSEEK_API_KEY", "").strip(),
            deepseek_base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip(
                "/"
            ),
            deepseek_model=os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash"),
            deepseek_thinking=_as_bool(os.getenv("DEEPSEEK_THINKING")),
            deepseek_timeout_seconds=float(os.getenv("DEEPSEEK_TIMEOUT_SECONDS", "60")),
            deepseek_max_retries=int(os.getenv("DEEPSEEK_MAX_RETRIES", "2")),
            deepseek_max_tokens=int(os.getenv("DEEPSEEK_MAX_TOKENS", "2200")),
            deepseek_daily_budget_usd=float(os.getenv("DEEPSEEK_DAILY_BUDGET_USD", "0")),
            deepseek_input_price_per_million_usd=float(
                os.getenv("DEEPSEEK_INPUT_PRICE_PER_MILLION_USD", "0")
            ),
            deepseek_output_price_per_million_usd=float(
                os.getenv("DEEPSEEK_OUTPUT_PRICE_PER_MILLION_USD", "0")
            ),
        )
        settings.ensure_local_directories()
        return settings

    @property
    def ai_cache_dir(self) -> Path:
        return self.data_dir / "cache" / "ai"

    def ensure_local_directories(self) -> None:
        """只创建本地运行目录；这些目录均被 .gitignore 排除。"""

        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        (self.data_dir / "raw").mkdir(parents=True, exist_ok=True)
        (self.data_dir / "cache").mkdir(parents=True, exist_ok=True)
        (self.data_dir / "private").mkdir(parents=True, exist_ok=True)
