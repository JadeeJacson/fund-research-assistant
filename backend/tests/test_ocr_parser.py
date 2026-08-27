from app.ocr import classify_page, parse_ocr_text
from app.providers import match_fund_catalog


def test_holding_screenshot_text_creates_review_drafts_only():
    text = "全部持有\n嘉实上证科创板芯片ETF联接C\n017470\n持有金额 1,250.00元\n持有收益 -86.35元"
    page_type, items = parse_ocr_text(text)
    assert page_type == "holdings"
    assert classify_page(text) == "holdings"
    assert items[0].kind == "holding"
    assert items[0].fund_code == "017470"
    assert items[0].amount == 1250
    assert items[0].displayed_profit == -86.35


def test_profit_rate_is_not_mistaken_for_profit_amount():
    text = "全部持有\n017470\n持有金额 250.00元\n收益率 -3.20%"
    _, items = parse_ocr_text(text)
    assert items[0].amount == 250
    assert items[0].displayed_profit is None


def test_candidate_screenshot_is_not_promoted_to_holding():
    text = "基金自选\n易方达机器人ETF联接A\n020972"
    page_type, items = parse_ocr_text(text)
    assert page_type == "candidates"
    assert items[0].kind == "candidate"


def test_alipay_name_only_screenshot_resolves_alias_and_positional_values():
    text = """全部持有
嘉实上证科创板芯片ETF联接C
基金
进阶理财
63.64
0.00
-13.72
-13.72
占比 2.44%
-17.73%
"""
    resolved = match_fund_catalog(
        text,
        [("017470", "嘉实上证科创板芯片ETF发起联接C")],
    )
    page_type, items = parse_ocr_text(text, resolved)

    assert page_type == "holdings"
    assert resolved[0][:2] == ("017470", "嘉实上证科创板芯片ETF发起联接C")
    assert items[0].fund_code == "017470"
    assert items[0].amount == 63.64
    assert items[0].displayed_profit == -13.72


def test_name_matching_selects_share_class_and_handles_common_name_aliases():
    text = """全部持有
景顺长城科创50联接C
易方达中概互联网ETF联接(QDII)C(人民币份额)
"""
    resolved = match_fund_catalog(
        text,
        [
            ("012835", "景顺长城上证科创板50成份指数型发起式证券投资基金联接A"),
            ("012836", "景顺长城上证科创板50成份指数型发起式证券投资基金联接C"),
            ("006327", "易方达中证海外中国互联网50ETF联接人民币A"),
            ("006328", "易方达中证海外中国互联网50ETF联接人民币C"),
        ],
    )

    assert {item[0] for item in resolved} == {"012836", "006328"}


def test_platform_product_without_underlying_fund_is_not_guessed():
    resolved = match_fund_catalog(
        "全部持有\n余额宝\n0.22\n0.00",
        [("000009", "易方达天天理财货币A")],
    )
    assert resolved == []


def test_later_platform_balance_is_not_used_as_fund_profit():
    text = """全部持有
持有收益
累计收益
易方达中概互联网ETF联接(QDII)C(人民币份额)
基金
进阶理财
250.87
+0.26
-49.13
-49.13
占比 9.62%
以上按照持有收益排序
余额宝
灵活取用
410.46
+0.02
+18.32
占比 15.74%
"""
    resolved = [("006328", "易方达中证海外中国互联网50ETF联接人民币C", 0.85)]
    _, items = parse_ocr_text(text, resolved)

    assert items[0].amount == 250.87
    assert items[0].displayed_profit == -49.13
