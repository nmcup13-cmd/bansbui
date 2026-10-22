"""สร้างรายงานประจำเดือนเป็น Markdown

ใช้:  python -m src.report 2026-03
ผล:   reports/monthly_report.md

ทุกตัวเลขมาจากฟังก์ชันใน src/metrics.py ไฟล์นี้ทำหน้าที่จัดรูปแบบเท่านั้น
"""
import re
import sys
from pathlib import Path

import pandas as pd

from src import metrics as m

OUT = Path(__file__).resolve().parent.parent / "reports" / "monthly_report.md"
THAI_MONTHS = ["มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน",
               "กรกฎาคม", "สิงหาคม", "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม"]


def thai_month(month: str) -> str:
    year, mm = month.split("-")
    return f"{THAI_MONTHS[int(mm) - 1]} {year}"


def baht(v: float) -> str:
    return f"{v:,.0f} บาท"


def build_report(df: pd.DataFrame, month: str) -> str:
    """คืนเนื้อหารายงาน Markdown ของเดือน 'YYYY-MM'"""
    this = m.orders_in_month(df, month)
    if this.empty:
        raise ValueError(f"ไม่มีข้อมูลเดือน {month}")
    prev_month = m.previous_month(month)
    prev = m.orders_in_month(df, prev_month)

    net = m.net_sales(this)
    lines = [
        f"# รายงานยอดขายประจำเดือน {thai_month(month)}",
        "",
        "บ้านสบาย ช็อป · ยอดขายสุทธิ = qty × unit_price × (1 − discount_pct/100) "
        "เฉพาะสถานะ \"จัดส่งสำเร็จ\" ไม่รวมค่าส่ง",
        "",
        "## สรุป",
        "",
        "| ตัวชี้วัด | ค่า |",
        "|---|---:|",
        f"| ยอดขายสุทธิ | {baht(net)} |",
    ]
    if prev.empty:
        lines.append(f"| เทียบเดือนก่อน ({thai_month(prev_month)}) | ไม่มีข้อมูลเดือนก่อน |")
    else:
        prev_net = m.net_sales(prev)
        change = net - prev_net
        pct = change / prev_net * 100 if prev_net else float("nan")
        lines.append(f"| ยอดขายสุทธิเดือนก่อน ({thai_month(prev_month)}) | {baht(prev_net)} |")
        lines.append(f"| เปลี่ยนแปลง | {change:+,.0f} บาท ({pct:+.2f}%) |")
    lines += [
        f"| คำสั่งซื้อทั้งหมด | {len(this):,} |",
        f"| อัตรายกเลิก | {m.cancel_rate(this):.2f}% |",
        f"| อัตราคืนสินค้า | {m.return_rate(this):.2f}% |",
        "",
        "## 5 สินค้าขายดี (ตามยอดขายสุทธิ)",
        "",
        "| อันดับ | รหัส | สินค้า | จำนวนชิ้น | ยอดขายสุทธิ |",
        "|---:|---|---|---:|---:|",
    ]
    for i, r in enumerate(m.top_products(this, 5).itertuples(), start=1):
        lines.append(f"| {i} | {r.product_id} | {r.product_name} | {r.qty:,} | {baht(r.net)} |")
    lines += [
        "",
        "อัตรายกเลิกและอัตราคืนสินค้า = จำนวนคำสั่งซื้อสถานะนั้น ÷ คำสั่งซื้อทั้งหมดของเดือน × 100",
        "",
    ]
    return "\n".join(lines)


def write_report(df: pd.DataFrame, month: str, out: Path = OUT) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(build_report(df, month), encoding="utf-8")
    return out


def main(argv: list[str]) -> int:
    if len(argv) != 1 or not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", argv[0]):
        print("ใช้: python -m src.report YYYY-MM  เช่น python -m src.report 2026-03", file=sys.stderr)
        return 2
    try:
        path = write_report(m.load_orders(), argv[0])
    except ValueError as e:
        print(e, file=sys.stderr)
        return 1
    print(f"บันทึกรายงานแล้ว: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
