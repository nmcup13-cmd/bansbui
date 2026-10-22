"""ฟังก์ชันคำนวณตัวชี้วัดของบ้านสบาย ช็อป

ทุกฟังก์ชันรับ DataFrame ที่ได้จาก load_orders() เป็นพารามิเตอร์แรก
นิยามตัวชี้วัดอยู่ใน CLAUDE.md
"""
from pathlib import Path

import pandas as pd

DATA = Path(__file__).resolve().parent.parent / "data"

DELIVERED = "จัดส่งสำเร็จ"
CANCELLED = "ยกเลิก"
RETURNED = "คืนสินค้า"
SHIP_BUCKETS = [("1-2", 1, 2), ("3-4", 3, 4), ("5-6", 5, 6), ("7+", 7, None)]


def load_orders(path: Path | str = DATA / "orders.csv") -> pd.DataFrame:
    """อ่าน orders.csv แล้วเพิ่มคอลัมน์ที่ใช้บ่อย: net, unit_cost, gp, month, date

    net และ gp คิดทุกแถว (ยังไม่กรองสถานะ) ฟังก์ชันตัวชี้วัดเป็นผู้กรอง "จัดส่งสำเร็จ" เอง
    unit_cost อ่านจาก products.csv ที่อยู่โฟลเดอร์เดียวกับไฟล์ orders
    """
    path = Path(path)
    df = pd.read_csv(path, encoding="utf-8-sig")
    df["status"] = df["status"].astype(str).str.strip()
    products = pd.read_csv(path.parent / "products.csv", encoding="utf-8-sig")
    df = df.merge(products[["product_id", "unit_cost"]], on="product_id", how="left", validate="m:1")
    df["net"] = df["qty"] * df["unit_price"] * (1 - df["discount_pct"] / 100)
    df["gp"] = df["net"] - df["qty"] * df["unit_cost"]
    df["month"] = df["order_datetime"].astype(str).str[:7]
    df["date"] = df["order_datetime"].astype(str).str[:10]
    return df


def _delivered(df: pd.DataFrame) -> pd.DataFrame:
    return df[df["status"] == DELIVERED]


def _between(df: pd.DataFrame, col: str, start: str | None, end: str | None) -> pd.Series:
    """mask ของแถวที่ col อยู่ในช่วง start..end (รวมทั้งสองฝั่ง) ค่า None = ไม่จำกัดฝั่งนั้น"""
    mask = pd.Series(True, index=df.index)
    if start is not None:
        mask &= df[col] >= start
    if end is not None:
        mask &= df[col] <= end
    return mask


def _rate(df: pd.DataFrame, status: str) -> float:
    """จำนวนแถวสถานะนั้น ÷ จำนวนคำสั่งซื้อทั้งหมดใน df × 100"""
    return float((df["status"] == status).mean() * 100) if len(df) else 0.0


def net_sales(df: pd.DataFrame) -> float:
    """ยอดขายสุทธิรวม (บาท)"""
    return float(_delivered(df)["net"].sum())


def gross_profit(df: pd.DataFrame) -> float:
    """กำไรขั้นต้นรวม (บาท)"""
    return float(_delivered(df)["gp"].sum())


def aov(df: pd.DataFrame) -> float:
    """ยอดขายสุทธิเฉลี่ยต่อคำสั่งซื้อที่จัดส่งสำเร็จ (บาท)"""
    orders = _delivered(df)["order_id"].nunique()
    return net_sales(df) / orders if orders else 0.0


def cancel_rate(df: pd.DataFrame) -> float:
    """อัตรายกเลิกของคำสั่งซื้อทั้งหมดใน df (เปอร์เซ็นต์ 0–100)"""
    return _rate(df, CANCELLED)


def monthly_sales(df: pd.DataFrame) -> pd.Series:
    """ยอดขายสุทธิรายเดือน index = 'YYYY-MM' เรียงตามเวลา"""
    return _delivered(df).groupby("month")["net"].sum().sort_index()


def orders_in_month(df: pd.DataFrame, month: str) -> pd.DataFrame:
    """คำสั่งซื้อทุกสถานะของเดือน 'YYYY-MM' (สำเนา ไม่กระทบ df เดิม)"""
    return df[df["month"] == month].copy()


def previous_month(month: str) -> str:
    """เดือนก่อนหน้าของ 'YYYY-MM' เช่น '2026-01' → '2025-12'"""
    return (pd.Period(month, freq="M") - 1).strftime("%Y-%m")


def top_products(df: pd.DataFrame, n: int = 5) -> pd.DataFrame:
    """สินค้าขายดีตามยอดขายสุทธิ คอลัมน์ product_id, product_name, qty, net เรียงจากมากไปน้อย"""
    return (_delivered(df).groupby(["product_id", "product_name"], as_index=False)
            .agg(qty=("qty", "sum"), net=("net", "sum"))
            .sort_values(["net", "product_id"], ascending=[False, True])
            .head(n).reset_index(drop=True))


def best_month(df: pd.DataFrame) -> str:
    """เดือนที่ยอดขายสุทธิสูงสุด ('YYYY-MM')"""
    return str(monthly_sales(df).idxmax())


def channel_share(df: pd.DataFrame, channel: str, start_month: str, end_month: str) -> float:
    """สัดส่วนยอดขายสุทธิของช่องทางในช่วงเดือน start_month..end_month (รวมทั้งสองเดือน) เป็นเปอร์เซ็นต์"""
    period = df[_between(df, "month", start_month, end_month)]
    total = net_sales(period)
    return net_sales(period[period["channel"] == channel]) / total * 100 if total else 0.0


def rating_by_ship_bucket(df: pd.DataFrame) -> dict[str, float]:
    """คะแนนรีวิวเฉลี่ยตามระยะส่ง คืน dict คีย์ '1-2', '3-4', '5-6', '7+'

    ใช้ทุกแถวที่มีทั้ง ship_days และ rating (รวมคำสั่งซื้อที่คืนสินค้าซึ่งได้รับของแล้ว)
    """
    rated = df.dropna(subset=["ship_days", "rating"])
    out = {}
    for key, lo, hi in SHIP_BUCKETS:
        in_bucket = rated["ship_days"] >= lo
        if hi is not None:
            in_bucket &= rated["ship_days"] <= hi
        out[key] = float(rated.loc[in_bucket, "rating"].mean())
    return out


def top_province(df: pd.DataFrame, region: str) -> str:
    """จังหวัดที่มียอดขายสุทธิสูงสุดในภูมิภาคที่ระบุ"""
    sales = _delivered(df[df["region"] == region]).groupby("province")["net"].sum()
    if sales.empty:
        raise ValueError(f"ไม่มียอดขายในภูมิภาค {region!r}")
    return str(sales.idxmax())


def avg_ship_days(df: pd.DataFrame, region: str | None = None, carrier: str | None = None,
                  start_date: str | None = None, end_date: str | None = None) -> float:
    """ระยะส่งเฉลี่ย (วัน) ตามตัวกรองที่ให้มา วันที่เป็น 'YYYY-MM-DD' และรวมทั้งสองวัน

    เฉลี่ยจากแถวที่มี ship_days (คำสั่งซื้อที่ยกเลิกไม่มีค่านี้จึงถูกตัดออกเอง)
    """
    mask = _between(df, "date", start_date, end_date)
    if region is not None:
        mask &= df["region"] == region
    if carrier is not None:
        mask &= df["carrier"] == carrier
    return float(df.loc[mask, "ship_days"].dropna().mean())


def return_rate(df: pd.DataFrame, product_id: str | None = None,
                start_date: str | None = None, end_date: str | None = None) -> float:
    """อัตราคืนสินค้า (เปอร์เซ็นต์) ของสินค้าและช่วงวันที่ที่ระบุ

    ตัวหาร = คำสั่งซื้อทั้งหมดในกลุ่ม รวมที่ยกเลิก ตามนิยามใน CLAUDE.md
    """
    mask = _between(df, "date", start_date, end_date)
    if product_id is not None:
        mask &= df["product_id"] == product_id
    return _rate(df[mask], RETURNED)
