from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from fundlab.domain.models import NavRecord


@dataclass(slots=True)
class NavValidationResult:
    records: list[NavRecord]
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return bool(self.records) and not self.errors


def validate_nav_records(
    records: list[NavRecord], *, today: date | None = None
) -> NavValidationResult:
    """检查净值日期、重复值和异常跳变，不静默修复财务数据。"""

    result = NavValidationResult(records=[])
    if not records:
        result.errors.append("净值数据为空")
        return result

    deduplicated: dict[date, NavRecord] = {}
    for record in sorted(records, key=lambda item: item.nav_date):
        previous = deduplicated.get(record.nav_date)
        if previous and abs(previous.return_nav - record.return_nav) > 1e-10:
            result.errors.append(f"{record.nav_date} 存在冲突净值")
            continue
        deduplicated[record.nav_date] = record
    result.records = list(deduplicated.values())

    for previous, current in zip(result.records, result.records[1:], strict=False):
        change = current.return_nav / previous.return_nav - 1
        if abs(change) > 0.20:
            result.warnings.append(
                f"{current.nav_date} 单日净值变化 {change:.1%}，需要核验分红、拆分或数据异常"
            )

    reference = today or date.today()
    stale_days = (reference - result.records[-1].nav_date).days
    if stale_days > 14:
        result.warnings.append(f"最新净值距今 {stale_days} 天，数据可能过期")
    if len(result.records) < 200:
        result.warnings.append("净值观察值少于 200 个，风险指标稳定性较弱")
    return result
