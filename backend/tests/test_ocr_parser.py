from app.ocr import classify_page, parse_ocr_text


def test_candidate_screenshot_text_parsing():
    text = "基金自选\n嘉实上证科创板芯片ETF联接C\n017470\n易方达机器人ETF联接A\n020972"
    page_type, items = parse_ocr_text(text)
    assert page_type == "candidates"
    assert {item.fund_code for item in items} == {"017470", "020972"}


def test_transaction_text_requires_review():
    text = "交易记录\n买入 基金 | 兴全恒裕债券A 1,000.00元\n2026-06-21 11:13:40"
    page_type, items = parse_ocr_text(text)
    assert classify_page(text) == "transactions"
    assert page_type == "transactions"
    assert items[0].kind == "transaction"
    assert items[0].issues


def test_active_tab_wins_over_other_navigation_labels():
    holding = "全部持有 收益明细 交易记录 资产构成 持有收益 兴全恒裕债券A"
    transaction = "全部持有 收益明细 交易记录 买入 基金|兴全恒裕债券A 1000元 卖出"
    assert classify_page(holding) == "holdings"
    assert classify_page(transaction) == "transactions"
