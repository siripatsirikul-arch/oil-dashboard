"""
Oil Price Scraper
- ราคาไทย: กรมธุรกิจพลังงาน (doeb.go.th) + Bangchak
- ราคาโลก: Yahoo Finance (ไม่ต้อง API key)
รันแล้วเขียนผลลงไฟล์ data/prices.json
"""

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# ─── helpers ────────────────────────────────────────────────────────────────

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )
}

def get(url, timeout=15, **kwargs):
    r = requests.get(url, headers=HEADERS, timeout=timeout, **kwargs)
    r.raise_for_status()
    return r

# ─── ราคาน้ำมันดิบโลก (Yahoo Finance) ──────────────────────────────────────

def fetch_global_prices() -> dict:
    """ดึงราคา Brent, WTI, Dubai จาก Yahoo Finance"""
    symbols = {
        "brent": "BZ=F",   # Brent Crude Futures
        "wti":   "CL=F",   # WTI Crude Futures
    }
    prices = {}
    for name, sym in symbols.items():
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?interval=1d&range=1d"
        try:
            data = get(url).json()
            price = data["chart"]["result"][0]["meta"]["regularMarketPrice"]
            prices[name] = round(price, 2)
            print(f"  ✓ {name.upper()}: ${price:.2f}")
        except Exception as e:
            print(f"  ✗ {name.upper()} failed: {e}")
            prices[name] = None

    # Dubai ไม่มีบน Yahoo Finance — ใช้ Brent - ~1 USD เป็น proxy
    if prices.get("brent"):
        prices["dubai"] = round(prices["brent"] - 1.0, 2)
    else:
        prices["dubai"] = None

    return prices


# ─── ราคาน้ำมันไทย (DOEB + Bangchak) ───────────────────────────────────────

# URL กรมธุรกิจพลังงาน — หน้าราคาน้ำมันวันนี้
DOEB_URL = "https://www.doeb.go.th/portals/0/popup_oil.php"
BANGCHAK_URL = "https://www.bangchak.co.th/th/oilprice"


def fetch_thai_prices_doeb() -> dict | None:
    """ดึงจาก DOEB (กรมธุรกิจพลังงาน)"""
    try:
        r = get(DOEB_URL)
        soup = BeautifulSoup(r.text, "html.parser")
        prices = {}

        # DOEB แสดงตารางราคา — ดึง row ที่มีชื่อน้ำมัน
        rows = soup.find_all("tr")
        for row in rows:
            cols = row.find_all("td")
            if len(cols) >= 2:
                name = cols[0].get_text(strip=True)
                val_text = cols[1].get_text(strip=True)
                # ดึงตัวเลขออกมา
                m = re.search(r"[\d.]+", val_text.replace(",", ""))
                if m:
                    val = float(m.group())
                    key = map_thai_oil_name(name)
                    if key:
                        prices[key] = val

        if prices:
            print(f"  ✓ DOEB: {len(prices)} items")
            return prices
    except Exception as e:
        print(f"  ✗ DOEB failed: {e}")
    return None


def fetch_thai_prices_bangchak() -> dict | None:
    """Fallback: ดึงจาก Bangchak"""
    try:
        r = get(BANGCHAK_URL)
        soup = BeautifulSoup(r.text, "html.parser")
        prices = {}

        # Bangchak ใช้ data attribute หรือ JSON ใน script tag
        # หา pattern ราคา เช่น "29.94" ใกล้กับชื่อน้ำมัน
        scripts = soup.find_all("script")
        for sc in scripts:
            text = sc.string or ""
            # ลองหา JSON ที่มีราคา
            if "diesel" in text.lower() or "gasohol" in text.lower():
                # ดึง key-value pairs
                matches = re.findall(r'"([^"]+)":\s*([\d.]+)', text)
                for k, v in matches:
                    mapped = map_thai_oil_name(k)
                    if mapped:
                        prices[mapped] = float(v)

        # Fallback: ดึงจาก visible text ในตาราง
        if not prices:
            for row in soup.find_all("tr"):
                cols = row.find_all("td")
                if len(cols) >= 2:
                    name = cols[0].get_text(strip=True)
                    val_text = cols[-1].get_text(strip=True)
                    m = re.search(r"([\d]{2}\.[\d]{2})", val_text)
                    if m:
                        key = map_thai_oil_name(name)
                        if key:
                            prices[key] = float(m.group())

        if prices:
            print(f"  ✓ Bangchak: {len(prices)} items")
            return prices
    except Exception as e:
        print(f"  ✗ Bangchak failed: {e}")
    return None


# ชื่อน้ำมันภาษาไทย → key มาตรฐาน
_NAME_MAP = {
    # ดีเซล
    "ดีเซล":        "diesel_b7",
    "diesel":       "diesel_b7",
    "b7":           "diesel_b7",
    "ไฮดีเซล":      "diesel_b7",
    # แก๊สโซฮอล์
    "แก๊สโซฮอล์95": "gsh95",
    "แก๊สโซฮอล์ 95": "gsh95",
    "gasohol95":    "gsh95",
    "gsh95":        "gsh95",
    "แก๊สโซฮอล์91": "gsh91",
    "แก๊สโซฮอล์ 91": "gsh91",
    "gsh91":        "gsh91",
    # E20 / E85
    "e20":          "e20",
    "แก๊สโซฮอล์e20": "e20",
    "e85":          "e85",
    "แก๊สโซฮอล์e85": "e85",
    # เบนซิน
    "เบนซิน95":     "benzin95",
    "benzin95":     "benzin95",
    "benzin":       "benzin95",
}

def map_thai_oil_name(raw: str) -> str | None:
    clean = raw.lower().replace(" ", "").replace("_", "")
    for k, v in _NAME_MAP.items():
        if k.replace(" ", "") in clean:
            return v
    return None


def fetch_thai_prices() -> dict:
    """ลอง DOEB ก่อน ถ้าไม่ได้ใช้ Bangchak"""
    prices = fetch_thai_prices_doeb()
    if not prices:
        prices = fetch_thai_prices_bangchak()
    if not prices:
        print("  ✗ ไม่สามารถดึงราคาไทยได้ — ใช้ fallback")
        # fallback ค่าล่าสุดที่รู้ (กรณี scraping blocked ชั่วคราว)
        prices = {
            "diesel_b7": 29.94,
            "gsh95":     31.05,
            "gsh91":     30.68,
            "e20":       27.84,
            "e85":       25.79,
            "benzin95":  40.14,
        }
    return prices


# ─── โหลดและ append ข้อมูลเก่า ──────────────────────────────────────────────

DATA_FILE = Path(__file__).parent.parent / "data" / "prices.json"

def load_existing() -> dict:
    if DATA_FILE.exists():
        with open(DATA_FILE) as f:
            return json.load(f)
    return {"history": [], "latest": {}}

def save(data: dict):
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"  ✓ บันทึกลง {DATA_FILE}")


# ─── main ────────────────────────────────────────────────────────────────────

def main():
    print("=== Oil Price Scraper ===")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    print("\n[1] ดึงราคาโลก...")
    global_prices = fetch_global_prices()

    print("\n[2] ดึงราคาไทย...")
    thai_prices = fetch_thai_prices()

    # รวมข้อมูล
    snapshot = {
        "date": today,
        "updated_at": now,
        "global": global_prices,
        "thai": thai_prices,
    }

    # โหลดข้อมูลเก่าแล้ว append
    data = load_existing()
    history = data.get("history", [])

    # ถ้าวันนี้มีข้อมูลแล้ว ให้อัพเดทแทน
    history = [h for h in history if h["date"] != today]
    history.append(snapshot)

    # เก็บแค่ 90 วันล่าสุด
    history = sorted(history, key=lambda x: x["date"])[-90:]

    output = {
        "latest": snapshot,
        "history": history,
        "meta": {
            "total_days": len(history),
            "first_date": history[0]["date"] if history else today,
            "last_updated": now,
        }
    }

    print("\n[3] บันทึกข้อมูล...")
    save(output)
    print(f"\n✅ สำเร็จ — {today}")


if __name__ == "__main__":
    main()
