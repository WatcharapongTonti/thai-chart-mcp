# ใช้งานจาก iPhone / เครื่องอื่น — ทำเป็น remote MCP

เป้าหมาย: ให้ Claude บน **iPhone, เว็บ, และ Desktop** เรียก `thai-chart` ได้เหมือนกันหมด

---

## ทำไมต้องทำแบบนี้ (และทำไมเปลี่ยนแหล่งข้อมูลไม่ช่วย)

ตอนนี้เซิร์ฟเวอร์รันแบบ **stdio** — Claude Desktop สั่งรันโปรแกรมบน Mac ของคุณโดยตรง
มันไม่มี URL **จึงไม่มีที่อยู่ให้เครื่องอื่นเรียกถึง** ไม่ว่าจะดึงข้อมูลจาก Yahoo, SET หรือที่ไหน

สิ่งที่ต้องเปลี่ยนคือ **ที่อยู่ของเซิร์ฟเวอร์** ไม่ใช่แหล่งข้อมูล:

```
เดิม:  Claude Desktop ──(รันโปรแกรม)──> server.py          [Mac เท่านั้น]
ใหม่:  Claude ทุกเครื่อง ──(HTTPS + token)──> server.py     [ทุกเครื่อง]
```

---

## ความเสี่ยงด้านความปลอดภัย — ประเมินตามจริง

เซิร์ฟเวอร์นี้ **อ่านข้อมูลราคาหุ้นสาธารณะแล้ววาดกราฟ** เท่านั้น

- ❌ ไม่มีคำสั่งเขียน/ลบอะไรทั้งนั้น
- ❌ ไม่แตะพอร์ตจริง ไม่ส่งคำสั่งซื้อขาย ไม่รู้จักบัญชีโบรกของคุณ
- ❌ ไม่เก็บข้อมูลส่วนตัวใด ๆ

**กรณีเลวร้ายที่สุดถ้ามีคนเดา URL เจอ: เขาได้ดูกราฟหุ้นไทยฟรี** — ไม่ใช่ศูนย์ แต่ต่ำมาก
สิ่งที่ token ป้องกันจริง ๆ คือการถูกยิงรัว ๆ จนโดนจำกัดโควตาจากแหล่งข้อมูล

> ⚠️ **แต่หลักการยังเดิม: ห้ามรันโดยไม่มี token** และถ้าวันไหนเพิ่มเครื่องมือที่
> อ่านไฟล์ในเครื่องหรือแตะข้อมูลส่วนตัว **การประเมินข้างบนนี้ใช้ไม่ได้อีกต่อไป** ต้องคิดใหม่ทั้งหมด

---

## วิธีที่ 1 — Cloudflare Tunnel บน Mac (ฟรี เริ่มที่นี่ก่อน)

ไม่ต้องมี IP สาธารณะ ไม่ต้องเปิด port ที่เราเตอร์ ได้ HTTPS ให้เสร็จ

### 1. สร้าง token

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

เก็บค่าที่ได้ไว้ — เรียกว่า `<TOKEN>` ต่อจากนี้

### 2. รันเซิร์ฟเวอร์

```bash
cd /Users/gla/Skill/thai-chart-mcp
THAI_CHART_TOKEN='<TOKEN>' .venv/bin/python server.py --http --port 8000
```

ควรเห็น:

```
[auth] เปิดการตรวจ bearer token แล้ว
[serve] http://127.0.0.1:8000/mcp
```

### 3. เปิด tunnel (หน้าต่าง Terminal ใหม่)

```bash
brew install cloudflared
cloudflared tunnel --url http://127.0.0.1:8000
```

จะได้ URL หน้าตาแบบ `https://xxxx-yyyy.trycloudflare.com` → **ที่อยู่ของ MCP คือ URL นั้น + `/mcp`**

> ⚠️ URL แบบนี้เปลี่ยนทุกครั้งที่รัน `cloudflared` ใหม่ ถ้าอยากได้ที่อยู่ถาวรต้องทำ
> named tunnel (ต้องมีโดเมนของตัวเอง) หรือใช้วิธีที่ 2

### 4. เพิ่มเป็น connector ใน Claude

ไปที่ **Settings → Connectors → Add custom connector** บน claude.ai แล้วใส่:

| ช่อง | ค่า |
|---|---|
| URL | `https://xxxx-yyyy.trycloudflare.com/mcp` |
| Authentication / Header | `Authorization: Bearer <TOKEN>` |

ตั้งที่เดียว **ใช้ได้ทุกเครื่องที่ล็อกอินบัญชีเดียวกัน รวม iPhone**

> หน้าตาเมนูและการรองรับ custom connector ขึ้นกับแพ็กเกจที่ใช้อยู่ — ถ้าไม่เห็นเมนูนี้
> แปลว่าบัญชียังไม่เปิดให้ใช้ ต้องใช้ผ่าน Desktop ไปก่อน

### ⚠️ ข้อจำกัดที่ต้องรู้ก่อนเลือกวิธีนี้

**Mac ต้องเปิดและไม่หลับ** ตอนที่เรียกใช้ ถ้า Mac หลับ = เรียกจาก iPhone ไม่ได้

กัน Mac หลับระหว่างรัน:

```bash
caffeinate -i cloudflared tunnel --url http://127.0.0.1:8000
```

(ปิดหน้าจอได้ แต่เครื่องต้องเสียบไฟและไม่ถูกสั่ง sleep)

---

## วิธีที่ 2 — VPS (เสียเงิน แต่เปิดตลอด 24 ชม.)

เหมาะถ้าอยากให้ **งานรีวิวพอร์ตรายสัปดาห์** (ที่รันบนคลาวด์เช้าวันเสาร์) เห็นกราฟด้วย
เพราะตอนนั้น Mac คุณอาจหลับอยู่

เครื่องเล็กสุดพอ (1 vCPU / 1 GB) ราคาประมาณ 4–6 USD ต่อเดือน

```bash
# บน VPS
git clone <repo หรือ scp โฟลเดอร์ขึ้นไป>
cd thai-chart-mcp && python3 install.py --no-config

# รันค้างไว้ด้วย systemd
sudo tee /etc/systemd/system/thai-chart.service >/dev/null <<'EOF'
[Unit]
Description=thai-chart MCP
After=network.target

[Service]
WorkingDirectory=/opt/thai-chart-mcp
Environment=THAI_CHART_TOKEN=<TOKEN>
ExecStart=/opt/thai-chart-mcp/.venv/bin/python server.py --http --host 127.0.0.1 --port 8000
Restart=always
User=www-data

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl enable --now thai-chart
```

แล้ววาง **Caddy** ไว้หน้า เพื่อให้ได้ TLS อัตโนมัติ:

```
chart.yourdomain.com {
    reverse_proxy 127.0.0.1:8000
}
```

> ⚠️ **ห้ามให้ `--host 0.0.0.0` โผล่ออกอินเทอร์เน็ตตรง ๆ** ให้ผูกกับ `127.0.0.1`
> แล้วให้ reverse proxy เป็นคนรับจากข้างนอกเสมอ

---

## วิธีที่ 3 — GitHub + Render (ฟรี, URL ถาวร, Mac หลับได้) ⭐

**นี่คือทางที่ตอบโจทย์ "ใช้บน iPhone" ได้ดีที่สุด** — ไม่ต้องเปิด Mac ค้าง ไม่ต้องจ่ายเงิน และ URL ไม่เปลี่ยน

> ⚠️ **GitHub ไม่ได้รันเซิร์ฟเวอร์ให้** — Pages เสิร์ฟไฟล์นิ่งอย่างเดียว ส่วน Actions เป็นงานที่รันแล้วจบ
> GitHub ทำหน้าที่ **เก็บโค้ด** ส่วน Render เป็นคน **รันจริง** โดยดึงโค้ดจาก GitHub ไป

### 1. ขึ้น GitHub

repo ถูก `git init` และ commit แรกไว้ให้แล้ว เหลือแค่สร้าง repo แล้ว push:

```bash
cd /Users/gla/Skill/thai-chart-mcp
gh repo create thai-chart-mcp --private --source=. --push
```

ยังไม่มี `gh` → `brew install gh && gh auth login` ก่อน
หรือสร้าง repo เปล่าบนเว็บแล้ว:

```bash
git remote add origin https://github.com/<ชื่อผู้ใช้>/thai-chart-mcp.git
git push -u origin main
```

> เลือก `--private` ไว้ก่อนก็ได้ โค้ดนี้ไม่มีความลับอยู่ข้างใน (token อ่านจาก environment
> variable ไม่ได้ฝังในโค้ด) จะเปิด public ภายหลังก็ได้

### 2. Deploy ไป Render

1. ไป [render.com](https://render.com) → สมัคร → เชื่อมบัญชี GitHub
2. **New → Blueprint** → เลือก repo `thai-chart-mcp`
3. Render อ่าน `render.yaml` แล้วตั้งค่าให้เอง รวมถึง **สุ่ม `THAI_CHART_TOKEN` ให้**
4. deploy เสร็จ ไปหน้า service → **Environment** → คัดลอกค่า `THAI_CHART_TOKEN`
5. URL ของ MCP คือ `https://thai-chart-mcp-xxxx.onrender.com/mcp`

### 3. เพิ่มเป็น connector

**Settings → Connectors → Add custom connector** ใส่ URL ข้างบน + header
`Authorization: Bearer <TOKEN ที่คัดลอกมา>`

### ข้อแลกเปลี่ยนของแพ็กเกจฟรี

| | |
|---|---|
| ✅ ฟรี / URL ถาวร / Mac หลับได้ / งานรีวิววันเสาร์เรียกได้ | |
| ⚠️ **ไม่มีคนใช้ ~15 นาทีจะหลับ** | ครั้งแรกที่เรียกหลังหลับจะช้าราว 30–60 วินาที (cold start) |
| ⚠️ เงื่อนไขแพ็กเกจฟรีเปลี่ยนได้ | เช็คหน้าเว็บ Render ล่าสุดก่อนตั้ง |

**cold start น่ารำคาญแต่ยอมรับได้** สำหรับการเรียกดูกราฟสัปดาห์ละไม่กี่ครั้ง
ถ้าทนไม่ไหวค่อยอัปเป็นแพ็กเกจเสียเงิน หรือย้ายไปวิธีที่ 2

### แก้โค้ดภายหลัง

```bash
git add -A && git commit -m "อธิบายสิ่งที่แก้" && git push
```

Render deploy ใหม่ให้อัตโนมัติ และ **GitHub Actions จะรันเทสต์ให้ทุกครั้งที่ push**
(วาดกราฟได้ไหม / เครื่องมือครบไหม / `weekly_chart` ส่งภาพผ่าน MCP ได้ไหม / Docker build ผ่านไหม)

---

## ตรวจว่าใช้ได้

```bash
# ต้องได้ 401
curl -s -o /dev/null -w "%{http_code}\n" -X POST https://<URL>/mcp \
  -H 'Content-Type: application/json' -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'

# ต้องได้ 200
curl -s -X POST https://<URL>/mcp \
  -H 'Authorization: Bearer <TOKEN>' \
  -H 'Content-Type: application/json' -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"t","version":"1"}}}'
```

ทดสอบบนเครื่องนี้แล้ว: ไม่มี token → **401** | token ผิด → **401** | token ถูก → **200**

---

## ตารางเทียบให้เลือก

| | Desktop (stdio) | Cloudflare Tunnel | **GitHub + Render** ⭐ | VPS |
|---|---|---|---|---|
| ใช้บน iPhone | ❌ | ✅ | ✅ | ✅ |
| ค่าใช้จ่าย | ฟรี | ฟรี | **ฟรี** | ~5 USD/เดือน |
| Mac ต้องเปิด | ✅ (ตอนใช้) | ✅ (ตลอดเวลาที่จะใช้) | **❌** | ❌ |
| ที่อยู่ถาวร | — | ❌ | **✅** | ✅ |
| งานรีวิวรายสัปดาห์เห็นกราฟ | ❌ | เฉพาะตอน Mac เปิด | **✅** | ✅ |
| ความเร็วตอนเรียก | เร็ว | เร็ว | **ช้า 30–60 วิ ถ้าเพิ่งหลับ** | เร็ว |
| ความยุ่งยากตอนตั้ง | ต่ำ | กลาง | กลาง | สูง |

**คำแนะนำ:** ถ้าโจทย์คือ **ใช้บน iPhone** ให้ไป **วิธีที่ 3 (GitHub + Render)** เลย
ฟรีเหมือน Tunnel แต่ไม่ต้องเปิด Mac ค้าง และ URL ไม่เปลี่ยน — แลกกับ cold start 30–60 วินาที

ใช้ไปสัก 2–3 สัปดาห์แล้วดูว่าได้หยิบขึ้นมาใช้บนมือถือจริงไหม
**ถ้าใช้บ่อยจน cold start กวนใจ ค่อยอัปเป็นแพ็กเกจเสียเงินหรือย้าย VPS — อย่าเพิ่งจ่ายตั้งแต่ยังไม่รู้ว่าจะใช้**

---

*เซิร์ฟเวอร์นี้แสดงข้อมูลราคาในอดีตเพื่อประกอบการวิเคราะห์เท่านั้น ไม่ใช่คำแนะนำการลงทุน*
