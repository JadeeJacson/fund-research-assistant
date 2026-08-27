from __future__ import annotations

import argparse

from app.providers import AkshareProvider


FUNDS = [
    ("017470", "国内指数/联接"),
    ("000001", "主动权益/混合"),
    ("019028", "债券"),
    ("013308", "QDII"),
    ("000216", "黄金/商品"),
    ("006289", "FOF"),
    ("000009", "货币"),
]


def main() -> int:
    parser = argparse.ArgumentParser(description="基金仓位决策台真实 AKShare 冒烟检查")
    parser.add_argument("--limit", type=int, default=len(FUNDS))
    args = parser.parse_args()
    provider = AkshareProvider()
    failed = 0
    for code, expected in FUNDS[: args.limit]:
        try:
            payload = provider.load_fund(code)
            total_points = len(payload.cumulative_nav)
            print(
                f"OK {code} expected={expected} actual={payload.fund_type}/{payload.subtype} "
                f"date={payload.cumulative_nav[-1][0] if total_points else 'none'} points={total_points} "
                f"quality={payload.quality_status} source={payload.source_name}"
            )
        except Exception as exc:
            failed += 1
            print(f"FAIL {code} expected={expected} error={type(exc).__name__}: {exc}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
