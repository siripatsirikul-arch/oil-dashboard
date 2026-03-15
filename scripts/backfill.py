"""
backfill.py — เติมข้อมูลราคาน้ำมันดิบโลกย้อนหลัง 1 ปีจาก Yahoo Finance
รันครั้งเดียว: python scripts/backfill.py
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import requests

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )
}

DATA_FILE = Path(__file__).parent.parent / "docs" / "data" / "prices.json"

SYMBOLS = {
    "brent": "BZ=F",
    "wti":   "CL=F",
}


def fetch_history(symbol: str, range_: str = "1y") -> dict[str, float]:
    """ดึงราคารายวันย้อนหลัง 1 ปี → {date_str: price}"""
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
        f"?interval=1d&range={range_}"
    )
    r = requests.get(url, headers=HEADERS, timeout=20)
    r.raise_for_status()
    result = r.json()["chart"]["result"][0]

    timestamps = result["timestamp"]
    closes = result["indicators"]["quote"][0]["close"]

    out = {}
    for ts, price in zip(timestamps, closes):
        if price is None:
            continue
        date_str = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
        out[date_str] = round(price, 2)
    return out


def load_existing() -> dict:
    if DATA_FILE.exists():
        with open(DATA_FILE) as f:
            return json.load(f)
    return {"history": [], "latest": {}}


def main():
    print("=== Backfill: ดึงราคาย้อนหลัง 1 ปี ===\n")

    print("[1] ดึง Brent...")
    brent_hist = fetch_history("BZ=F")
    print(f"    ✓ {len(brent_hist)} วัน")

    print("[2] ดึง WTI...")
    wti_hist = fetch_history("CL=F")
    print(f"    ✓ {len(wti_hist)} วัน")

    # รวม dates จากทั้งสอง
    all_dates = sorted(set(brent_hist) | set(wti_hist))
    print(f"\n[3] รวมข้อมูล {len(all_dates)} วัน ({all_dates[0]} → {all_dates[-1]})")

    # โหลด existing (เพื่อเอา thai prices ที่มีอยู่)
    existing = load_existing()
    thai_by_date = {h["date"]: h.get("thai", {}) for h in existing.get("history", [])}

    # สร้าง history entries ใหม่
    new_history = []
    for date in all_dates:
        brent = brent_hist.get(date)
        wti   = wti_hist.get(date)
        dubai = round(brent - 1.0, 2) if brent else None

        new_history.append({
            "date": date,
            "updated_at": date + "T06:00:00Z",
            "global": {"brent": brent, "wti": wti, "dubai": dubai},
            "thai": thai_by_date.get(date, {}),
        })

    # Merge กับ thai-only entries ที่ไม่มีใน Yahoo (เก็บ thai data ไว้)
    existing_dates = {h["date"] for h in new_history}
    for h in existing.get("history", []):
        if h["date"] not in existing_dates and h.get("thai"):
            new_history.append(h)

    new_history = sorted(new_history, key=lambda x: x["date"])[-365:]

    # Forward-fill Thai prices: วันที่ไม่มีข้อมูล ให้ใช้ค่าล่าสุด
    last_thai = {}
    for entry in new_history:
        if entry["thai"]:
            last_thai = entry["thai"]
        elif last_thai:
            entry["thai"] = last_thai

    # Backward-fill: ช่วงก่อนจุดข้อมูลแรก ใช้ค่าแรกที่มี
    first_thai = next((h["thai"] for h in new_history if h["thai"]), {})
    for entry in new_history:
        if not entry["thai"] and first_thai:
            entry["thai"] = first_thai

    filled = sum(1 for h in new_history if h["thai"])
    print(f"    Thai prices filled: {filled}/{len(new_history)} วัน")

    latest = existing.get("latest", new_history[-1] if new_history else {})

    output = {
        "latest": latest,
        "history": new_history,
        "meta": {
            "total_days": len(new_history),
            "first_date": new_history[0]["date"] if new_history else "",
            "last_updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
    }

    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n✅ บันทึกแล้ว → {DATA_FILE}")
    print(f"   {new_history[0]['date']} → {new_history[-1]['date']} ({len(new_history)} จุด)")


if __name__ == "__main__":
    main()
