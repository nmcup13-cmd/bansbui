"""รายงานประจำเดือน"""
import pytest

from src import metrics as m
from src import report


@pytest.fixture(scope="module")
def df():
    return m.load_orders()


def test_report_march_2026(df):
    text = report.build_report(df, "2026-03")
    assert "| ยอดขายสุทธิ | 1,147,155 บาท |" in text
    assert "กุมภาพันธ์ 2026" in text            # เทียบเดือนก่อน
    assert "| อัตรายกเลิก |" in text
    assert "| อัตราคืนสินค้า |" in text
    assert text.count("\n| ") - text.count("\n|---") >= 5  # มีแถวสินค้าขายดี


def test_report_numbers_come_from_metrics(df):
    month = m.orders_in_month(df, "2026-03")
    text = report.build_report(df, "2026-03")
    assert f"{m.cancel_rate(month):.2f}%" in text
    assert f"{m.return_rate(month):.2f}%" in text
    top = m.top_products(month, 5)
    assert len(top) == 5
    assert list(top["net"]) == sorted(top["net"], reverse=True)
    assert top.iloc[0]["product_name"] in text


def test_report_first_month_has_no_previous(df):
    assert "ไม่มีข้อมูลเดือนก่อน" in report.build_report(df, "2025-10")


def test_report_writes_file(df, tmp_path):
    out = report.write_report(df, "2026-03", tmp_path / "monthly_report.md")
    assert "1,147,155 บาท" in out.read_text(encoding="utf-8")


def test_report_unknown_month(df):
    with pytest.raises(ValueError):
        report.build_report(df, "2030-01")


def test_previous_month():
    assert m.previous_month("2026-01") == "2025-12"
    assert m.previous_month("2026-03") == "2026-02"
