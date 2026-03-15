# 🛢️ Oil Price Live Dashboard

Dashboard ราคาน้ำมันอัพเดทอัตโนมัติทุก 6 ชั่วโมง โดยไม่ต้องมี server
ใช้ **GitHub Actions** (scrape + commit) + **GitHub Pages** (host)

---

## 📁 โครงสร้างไฟล์

```
oil-dashboard/
├── .github/
│   └── workflows/
│       └── update-prices.yml   ← Action รันทุก 6 ชม.
├── scripts/
│   └── scrape.py               ← Python scraper (DOEB + Yahoo Finance)
├── data/
│   └── prices.json             ← ข้อมูลราคา (auto-updated)
├── docs/
│   └── index.html              ← Dashboard หน้าเว็บ
└── requirements.txt
```

---

## 🚀 Setup ทีละขั้น (ใช้เวลา ~10 นาที)

### ขั้น 1 — สร้าง GitHub repo

1. ไปที่ https://github.com/new
2. ตั้งชื่อ repo เช่น `oil-dashboard`
3. เลือก **Public** (GitHub Pages ฟรีแค่ Public)
4. กด **Create repository**

### ขั้น 2 — Push โค้ดขึ้น

```bash
git init
git add .
git commit -m "initial commit"
git branch -M main
git remote add origin https://github.com/<USERNAME>/oil-dashboard.git
git push -u origin main
```

### ขั้น 3 — เปิด GitHub Pages

1. ไปที่ repo → **Settings** → **Pages**
2. Source: `Deploy from a branch`
3. Branch: `main` / Folder: `/docs`
4. กด **Save**
5. รอ 1-2 นาที จะได้ URL เช่น `https://<USERNAME>.github.io/oil-dashboard`

### ขั้น 4 — ให้ Actions มีสิทธิ์ commit

1. ไปที่ repo → **Settings** → **Actions** → **General**
2. เลื่อนลงหา **Workflow permissions**
3. เลือก **Read and write permissions**
4. กด **Save**

### ขั้น 5 — ทดสอบรัน scraper ครั้งแรก

1. ไปที่ **Actions** tab
2. เลือก `Update Oil Prices`
3. กด **Run workflow** → **Run workflow**
4. รอ 1-2 นาที ดู log ว่าผ่าน
5. เช็ค `data/prices.json` ว่ามีข้อมูลใหม่

---

## ⏰ Schedule

Action รันอัตโนมัติตาม cron `0 0,6,12,18 * * *` (UTC):

| UTC   | เวลาไทย |
|-------|---------|
| 00:00 | 07:00   |
| 06:00 | 13:00   |
| 12:00 | 19:00   |
| 18:00 | 01:00   |

---

## 🔧 แก้ไข scraper

ถ้า DOEB เปลี่ยน HTML structure → แก้ฟังก์ชัน `fetch_thai_prices_doeb()` ใน `scripts/scrape.py`

ดู selector ใหม่ได้โดย:
```bash
python3 -c "
import requests; from bs4 import BeautifulSoup
r = requests.get('https://www.doeb.go.th/portals/0/popup_oil.php')
soup = BeautifulSoup(r.text, 'html.parser')
print(soup.prettify()[:3000])
"
```

---

## 📊 ข้อมูลใน prices.json

```json
{
  "latest": {
    "date": "2026-03-15",
    "global": { "brent": 100.0, "wti": 98.7, "dubai": 99.0 },
    "thai":   { "diesel_b7": 29.94, "gsh95": 31.05, ... }
  },
  "history": [ ...90 วันล่าสุด... ],
  "meta": { "last_updated": "..." }
}
```

---

## 🐛 Troubleshooting

| ปัญหา | วิธีแก้ |
|-------|---------|
| Action fail: `Permission denied` | ตรวจสอบ Settings → Actions → Workflow permissions |
| ราคาไทยเป็น fallback ทุกครั้ง | DOEB อาจ block bot — ลอง scrape Bangchak แทน |
| หน้าเว็บ 404 | ตรวจ Settings → Pages ว่า source ถูกไหม |
| ราคาไม่อัพเดท | เช็ค Actions log ว่า git commit มีข้อความ "nothing to commit" ไหม |
