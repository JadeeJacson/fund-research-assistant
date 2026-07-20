from __future__ import annotations

from pathlib import Path


def load_prompt(project_root: Path, relative_path: str) -> str:
    path = project_root / "prompts" / relative_path
    if not path.exists():
        raise FileNotFoundError(f"Prompt 文件不存在：{path}")
    return path.read_text(encoding="utf-8").strip()
