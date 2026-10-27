# thai-chart-mcp

MCP server เล็ก ๆ ที่ **วาดกราฟรายสัปดาห์ของหุ้นไทยแล้วส่งเป็นภาพให้ Claude ดู** — เพื่อให้ Claude ทำ technical analysis ได้โดยไม่ต้องให้คุณแคปหน้าจอเองทุกครั้ง

---

## ทำไมไม่ใช่ TradingView MCP

สั้น ๆ คือ **ใช้ TradingView ไม่ได้ และไม่จำเป็นต้องใช้**

1. **TradingView ไม่มี public API สำหรับดึงภาพกราฟ** — ที่มีคือ widget embed ซึ่งไว้ฝังในเว็บ ไม่ใช่ไว้ให้โปรแกรมดึงภาพ
2. **การ scrape หน้าเว็บเขาผิด ToS** — เซิร์ฟเวอร์ที่สร้างบนฐานนั้นจะพังเมื่อไรก็ได้ และไม่ควรสร้างตั้งแต่แรก
3. **สิ่งที่ต้องการจริง ๆ ไม่ใช่ "ภาพจาก TradingView" แต่คือ "กราฟรายสัปดาห์ที่ถูกต้อง"** — ซึ่งสร้างเองได้จากข้อมูลราคา

ตัวนี้เลยดึง **ข้อมูลราคา OHLCV** จากแหล่งที่เปิดให้ใช้ แล้ว **วาดกราฟเอง** ด้วย `mplfinance`

**ข้อดีที่ได้มาฟรี ๆ จากการวาดเอง:**

- คุมได้เองว่าจะใส่ MA เส้นไหน (ตั้งไว้ที่ **20 / 50 / 200 สัปดาห์** ตามที่ technical analysis ต้องการ)
- **ขีดเส้น stop loss ลงบนกราฟได้** — ส่ง `levels=[70, 66]` แล้วเห็นเลยว่าราคาอยู่ตรงไหนเทียบจุดตัดขาดทุน
- ได้ **ตัวเลขจริง** กลับมาพร้อมภาพ (ราคาอยู่เหนือ/ใต้ MA กี่ %, ช่วง 52 สัปดาห์, วอลุ่มเทียบค่าเฉลี่ย) → Claude ไม่ต้องเดาค่าจากการมองภาพ ซึ่งเป็นจุดที่ AI อ่านกราฟผิดบ่อยที่สุด

---

## ติดตั้ง — คำสั่งเดียว

ต้องมี **Python 3.10 ขึ้นไป**

```bash
cd /path/to/thai-chart-mcp
python3 install.py
```

สคริปต์จะทำให้ครบทั้ง 4 ขั้น: สร้าง `.venv` → ติดตั้ง library → ทดสอบว่าวาดกราฟได้จริง →
เพิ่ม `thai-chart` เข้า config ของ Claude Desktop

**ปลอดภัยกับ config เดิม:** สำรองไฟล์เก่าไว้ก่อนเสมอ (`claude_desktop_config.backup-<วันเวลา>.json`)
แก้เฉพาะคีย์ `thai-chart` **MCP server ตัวอื่นที่มีอยู่แล้วไม่ถูกแตะ** และรันซ้ำได้ไม่พัง

ตัวเลือก:

```bash
python3 install.py --no-config      # ติดตั้งอย่างเดียว ไม่แตะ config
python3 install.py --print-config   # แสดง config ที่ต้องใส่ แล้วจบ (ใส่เองด้วยมือ)
```

เสร็จแล้ว **ปิด Claude Desktop ให้สนิทแล้วเปิดใหม่** (ปิดแค่หน้าต่างไม่พอ — ต้อง Quit จริง ๆ)

### ติดตั้งเองทีละขั้น (ถ้าไม่อยากใช้สคริปต์)

```bash
cd thai-chart-mcp
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python3 test_render.py             # ได้ไฟล์ test_output.png
```

ทดสอบว่าดึงข้อมูลจริงได้:

```bash
python3 -c "from server import _fetch_daily, to_weekly; print(to_weekly(_fetch_daily('TOP', 5)).tail())"
```

---

## ต่อกับ Claude

### วิธีที่ 1 — รันบนเครื่องตัวเอง (แนะนำ)

เซิร์ฟเวอร์รันบนเครื่องคุณ ใช้เน็ตของคุณ และ Claude เรียกผ่าน Claude Desktop

แก้ไฟล์ config ของ Claude Desktop:

- **macOS** — `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows** — `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "thai-chart": {
      "command": "/absolute/path/to/thai-chart-mcp/.venv/bin/python",
      "args": ["/absolute/path/to/thai-chart-mcp/server.py"]
    }
  }
}
```

> ⚠️ ต้องใส่ **path เต็ม** ทั้งสองช่อง และต้องเป็น python ใน `.venv` ไม่ใช่ `python3` เฉย ๆ
> ไม่งั้นมันจะหา library ไม่เจอ — เป็นสาเหตุอันดับหนึ่งที่ MCP server ไม่ขึ้น

ปิดแล้วเปิด Claude Desktop ใหม่ → ควรเห็น `thai-chart` ในรายการเครื่องมือ

### วิธีที่ 2 — self-host เป็น remote MCP

```bash
python3 server.py --http --host 0.0.0.0 --port 8000
```

แล้วเพิ่มเป็น custom connector ที่ `https://<โดเมนของคุณ>/mcp`

> ⚠️ ถ้าเปิดออกอินเทอร์เน็ต **ต้องมี reverse proxy + TLS + auth** อย่างน้อยที่สุด
> อย่าเปิด port ตรง ๆ และจำไว้ว่าบางเครือข่ายบล็อกโดเมนที่ไม่อยู่ใน allowlist
> (ซึ่งเป็นสาเหตุที่ TradingView กับ settrade ต่อไม่ได้ตั้งแต่แรก)

---

## เครื่องมือที่มี

### `weekly_chart(symbol, years=5, weeks_shown=160, levels=None)`

วาดกราฟแท่งเทียนรายสัปดาห์ + MA 20/50/200 สัปดาห์ + วอลุ่ม คืน **ภาพ PNG พร้อมสรุปตัวเลข**

```
weekly_chart("TOP", levels=[70, 66])
weekly_chart("KKP", weeks_shown=100, levels=[105])
```

### `weekly_table(symbol, weeks=30)`

ตาราง OHLCV + MA รายสัปดาห์เป็นข้อความ — ใช้เมื่อต้องการตัวเลขแม่น ๆ แทนการอ่านจากภาพ

### `compare_closes(symbols, weeks=12)`

เทียบราคาปิดรายสัปดาห์หลายตัวในตารางเดียว

```
compare_closes(["TOP", "OR", "KKP"], weeks=16)
```

---

## เรื่องชื่อย่อหุ้น

| ประเภท | ใส่แบบนี้ | ระบบแปลงเป็น |
|---|---|---|
| หุ้นไทย | `TOP`, `KKP`, `DIF`, `OR`, `BDMS`, `WP`, `GULF` | `TOP.BK` ฯลฯ |
| ดัชนี/ETF ต่างประเทศ | `^GSPC`, `SPY`, `QQQ` | ใช้ตรง ๆ |

**ข้อจำกัดที่ต้องรู้:** **DR อย่าง SP50001 ไม่มีบน Yahoo Finance** — ถ้าอยากดูกราฟของสิ่งที่ DR ตัวนั้นอ้างอิง ให้ใช้ `^GSPC` หรือ `SPY` แทน แล้วจำไว้ว่าราคา DR จริงจะต่างออกไปตามค่าเงินบาท

ข้อมูลจาก Yahoo Finance เป็นข้อมูลฟรี **อาจมีคลาดเคลื่อนหรือล่าช้า** — ก่อนส่งคำสั่งซื้อขายจริงให้ยึดราคาในแอปโบรกเกอร์เสมอ

---

## ถ้าไม่ขึ้นใน Claude

| อาการ | สาเหตุที่พบบ่อย |
|---|---|
| ไม่เห็น server เลย | path ใน config ไม่ใช่ path เต็ม หรือชี้ไปที่ python นอก `.venv` |
| server ขึ้นแต่เรียกแล้ว error | ยังไม่ได้ `pip install -r requirements.txt` ใน venv นั้น |
| `ไม่พบข้อมูลราคาของ ...` | ชื่อย่อผิด หรือหลักทรัพย์นั้นไม่มีบน Yahoo (เช่น DR) |
| `ModuleNotFoundError: mcp.server.fastmcp` | MCP SDK เวอร์ชัน 2 — โค้ดรองรับแล้วทั้งสองรุ่น ถ้ายังเจอให้ `pip install -U mcp` |
| กราฟออกมาแต่เส้น MA200 หาย | ข้อมูลไม่ถึง 200 สัปดาห์ → เพิ่ม `years` เป็น 6–7 |

---

*เครื่องมือนี้แสดงข้อมูลราคาในอดีตเพื่อประกอบการวิเคราะห์เท่านั้น ไม่ใช่คำแนะนำการลงทุน*

---

## บันทึกการแก้ไข

**v1.1**
- **แก้บั๊ก `weekly_chart` ใช้งานไม่ได้บน MCP SDK 2.x** — SDK รุ่นใหม่ serialize ออบเจกต์ `Image`
  ที่อยู่ใน list ไม่ได้ (`PydanticSerializationError`) ทำให้เครื่องมือนี้ error ทุกครั้งขณะที่
  `weekly_table` ทำงานปกติ → แปลงเป็น `ImageContent` ก่อนส่ง (ยัง fallback ให้ SDK 1.x)
- **เตือนเมื่อแท่งสุดท้ายยังไม่ปิดสัปดาห์** — เช่น ดูวันอังคาร แท่ง "สัปดาห์นี้" มีแค่ 2 วันทำการ
  ถ้าเอาไปใช้เป็น "ราคาปิดรายสัปดาห์" ตัดสินใจเรื่อง stop จะผิด ตอนนี้สรุปตัวเลขจะขึ้น ⚠️ บอกให้เอง
