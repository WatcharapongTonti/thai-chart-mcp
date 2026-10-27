"""
thai-chart-mcp — MCP server ที่วาดกราฟรายสัปดาห์ของหุ้นไทยให้ Claude ดูได้

ทำไมไม่ใช้ TradingView:
  TradingView ไม่มี public API สำหรับดึงภาพกราฟ และการ scrape หน้าเว็บของเขา
  ผิดเงื่อนไขการใช้งาน (ToS) เซิร์ฟเวอร์ตัวนี้จึงดึง "ข้อมูลราคา OHLCV"
  จากแหล่งข้อมูลที่เปิดให้ใช้ แล้ว *วาดกราฟเอง* ด้วย mplfinance
  ผลที่ได้ดีกว่าสำหรับการวิเคราะห์ เพราะเราคุมได้เองว่าจะใส่ MA เส้นไหน
  ช่วงเวลาเท่าไร และขีดเส้น stop loss ตรงไหน

Transport:
  stdio (ค่าเริ่มต้น) — สำหรับรันบนเครื่องตัวเอง ต่อกับ Claude Desktop / Claude Code
  http                — สำหรับ self-host เป็น remote MCP:  python server.py --http --port 8000
"""

from __future__ import annotations

import argparse
import base64
import io
import os
from datetime import datetime
from typing import Any

import matplotlib

matplotlib.use("Agg")  # ต้องตั้งก่อน import pyplot เสมอ (ไม่มีหน้าจอ)

import matplotlib.pyplot as plt  # noqa: E402
import mplfinance as mpf  # noqa: E402
import pandas as pd  # noqa: E402

# MCP SDK 2.x เปลี่ยนชื่อ FastMCP เป็น MCPServer — รองรับทั้งสองรุ่น
try:
    from mcp.server.mcpserver import Image, MCPServer as _Server  # SDK >= 2.0
except ImportError:  # pragma: no cover - เส้นทางสำหรับ SDK 1.x
    from mcp.server.fastmcp import FastMCP as _Server, Image  # type: ignore

mcp = _Server("thai-chart")


def _image_block(png: bytes):
    """แปลง PNG เป็น content block ที่ส่งผ่าน MCP ได้

    SDK 2.x ไม่ serialize ออบเจกต์ Image ที่อยู่ใน list โดยตรง
    (PydanticSerializationError) ต้องแปลงเป็น ImageContent ก่อน
    SDK 1.x รับ Image ตรง ๆ ได้ จึง fallback ให้
    """
    img = Image(data=png, format="png")
    to_content = getattr(img, "to_image_content", None)
    return to_content() if to_content else img

# หุ้นไทยบน Yahoo Finance ใช้ suffix .BK — ส่วนดัชนี/ETF ต่างประเทศใช้ ticker ตรง ๆ
SET_SUFFIX = ".BK"
NON_SET = {"^GSPC", "^NDX", "^DJI", "SPY", "QQQ", "^SET.BK"}

# จำนวนสัปดาห์ของเส้นค่าเฉลี่ย (weekly timeframe)
MA_WEEKS = (20, 50, 200)


def _resolve(symbol: str) -> str:
    """แปลงชื่อหุ้นเป็น ticker ของ Yahoo: TOP -> TOP.BK, SPY -> SPY"""
    s = symbol.strip().upper()
    if s in NON_SET or s.startswith("^") or "." in s:
        return s
    return s + SET_SUFFIX


def _fetch_daily(symbol: str, years: int) -> pd.DataFrame:
    """ดึงราคารายวันแล้วคืนเป็น DataFrame (Open/High/Low/Close/Volume)"""
    import yfinance as yf

    ticker = _resolve(symbol)
    df = yf.download(
        ticker,
        period=f"{max(years, 1)}y",
        interval="1d",
        auto_adjust=False,
        progress=False,
        threads=False,
    )
    if df is None or df.empty:
        raise ValueError(
            f"ไม่พบข้อมูลราคาของ {symbol} (ticker ที่ลอง: {ticker}) — "
            "ตรวจชื่อย่อ หรือหลักทรัพย์นี้อาจไม่มีบน Yahoo Finance เช่น DR บางตัว"
        )
    # yfinance รุ่นใหม่คืน MultiIndex column เมื่อโหลดหลายตัว — ปรับให้แบนเสมอ
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df[["Open", "High", "Low", "Close", "Volume"]].dropna(how="all")
    df.index = pd.to_datetime(df.index)
    return df


def to_weekly(daily: pd.DataFrame) -> pd.DataFrame:
    """ยุบราคารายวันเป็นรายสัปดาห์ (ปิดวันศุกร์) — แยกออกมาเพื่อให้เทสต์ได้"""
    weekly = daily.resample("W-FRI").agg(
        {
            "Open": "first",
            "High": "max",
            "Low": "min",
            "Close": "last",
            "Volume": "sum",
        }
    )
    return weekly.dropna(subset=["Open", "High", "Low", "Close"])


def render_weekly_chart(
    weekly: pd.DataFrame,
    symbol: str,
    levels: list[float] | None = None,
    weeks_shown: int = 160,
) -> bytes:
    """วาด candlestick รายสัปดาห์ + MA20/50/200 + volume คืนเป็น PNG bytes

    MA คำนวณจากข้อมูลเต็มก่อน แล้วค่อยตัดช่วงที่จะแสดง
    เพื่อให้เส้น MA200 ไม่ขาดหัวตอนซูมเข้า
    """
    df = weekly.copy()
    for n in MA_WEEKS:
        df[f"MA{n}"] = df["Close"].rolling(n).mean()

    view = df.tail(weeks_shown)
    if view.empty:
        raise ValueError("ไม่มีข้อมูลพอจะวาดกราฟ")

    addplots = []
    colors = {20: "#4C9BE8", 50: "#E8A33D", 200: "#D45B6A"}
    for n in MA_WEEKS:
        col = view[f"MA{n}"]
        if col.notna().any():
            addplots.append(
                mpf.make_addplot(col, color=colors[n], width=1.3, label=f"MA{n}w")
            )

    hlines = None
    if levels:
        vals = [float(v) for v in levels]
        hlines = dict(
            hlines=vals,
            colors=["#9AA0A6"] * len(vals),
            linestyle="--",
            linewidths=1.0,
        )

    style = mpf.make_mpf_style(
        base_mpf_style="charles",
        rc={
            "font.size": 11,
            "axes.grid": True,
            "grid.alpha": 0.25,
        },
    )

    last = view.iloc[-1]
    title = (
        f"\n{symbol.upper()} — Weekly  |  last {last['Close']:.2f}  "
        f"|  {view.index[0]:%b %Y} – {view.index[-1]:%d %b %Y}  "
        f"|  {len(view)} weeks"
    )

    buf = io.BytesIO()
    kwargs: dict[str, Any] = dict(
        type="candle",
        volume=True,
        style=style,
        addplot=addplots,
        figsize=(16, 9),
        title=title,
        tight_layout=True,
        savefig=dict(fname=buf, dpi=130, bbox_inches="tight"),
    )
    if hlines:
        kwargs["hlines"] = hlines

    mpf.plot(view, **kwargs)
    plt.close("all")
    buf.seek(0)
    return buf.read()


def _summary(weekly: pd.DataFrame, symbol: str) -> str:
    """สรุปตัวเลขสำคัญเป็นข้อความ — ให้ Claude อ้างอิงตัวเลขได้โดยไม่ต้องเดาจากภาพ"""
    df = weekly.copy()
    for n in MA_WEEKS:
        df[f"MA{n}"] = df["Close"].rolling(n).mean()
    last = df.iloc[-1]
    close = float(last["Close"])

    lines = [
        f"{symbol.upper()} — weekly, {len(df)} แท่ง, ล่าสุด {df.index[-1]:%Y-%m-%d}",
        f"ปิด {close:.2f} | สัปดาห์นี้ H {float(last['High']):.2f} / L {float(last['Low']):.2f}",
    ]

    # แท่งสุดท้ายอาจเป็นสัปดาห์ที่ยังไม่ปิด — ต้องเตือน ไม่งั้นจะถูกใช้เป็น
    # "ราคาปิดรายสัปดาห์" ในการตัดสินใจเรื่อง stop ทั้งที่สัปดาห์ยังไม่จบ
    week_end = df.index[-1].normalize()
    today = pd.Timestamp.now(tz=df.index.tz).normalize() if df.index.tz else pd.Timestamp.now().normalize()
    if week_end > today:
        days_left = int((week_end - today).days)
        lines.append(
            f"⚠️ แท่งสุดท้ายยังไม่ปิดสัปดาห์ (ป้าย {week_end:%Y-%m-%d}, เหลืออีก {days_left} วัน) "
            "— อย่าใช้เป็นราคาปิดรายสัปดาห์ในการตัดสินใจเรื่อง stop"
        )
    for n in MA_WEEKS:
        v = last.get(f"MA{n}")
        if pd.notna(v):
            pct = (close / float(v) - 1) * 100
            pos = "เหนือ" if pct >= 0 else "ใต้"
            lines.append(f"MA{n}w = {float(v):.2f} → ราคาอยู่{pos} {abs(pct):.1f}%")
        else:
            lines.append(f"MA{n}w = ยังไม่มีข้อมูลพอ (ต้องการ {n} สัปดาห์)")

    for win, label in ((52, "52 สัปดาห์"), (len(df), "ทั้งชุดข้อมูล")):
        seg = df.tail(win)
        hi, lo = float(seg["High"].max()), float(seg["Low"].min())
        lines.append(
            f"ช่วง {label}: {lo:.2f} – {hi:.2f} "
            f"(ราคาอยู่ที่ {(close - lo) / (hi - lo) * 100:.0f}% ของช่วง)"
        )

    v12 = df["Volume"].tail(12).mean()
    lines.append(
        f"วอลุ่มสัปดาห์ล่าสุด {float(last['Volume']):,.0f} "
        f"เทียบค่าเฉลี่ย 12 สัปดาห์ {float(v12):,.0f} "
        f"({float(last['Volume']) / float(v12) * 100:.0f}%)"
    )
    return "\n".join(lines)


@mcp.tool()
def weekly_chart(
    symbol: str,
    years: int = 5,
    weeks_shown: int = 160,
    levels: list[float] | None = None,
) -> list[Any]:
    """วาดกราฟแท่งเทียนรายสัปดาห์ของหุ้นไทย พร้อม MA 20/50/200 สัปดาห์ และวอลุ่ม

    Args:
        symbol: ชื่อย่อหุ้น เช่น TOP, KKP, DIF (ใส่ .BK เองก็ได้) หรือ ^GSPC, SPY
        years: จำนวนปีย้อนหลังที่จะดึง (ค่าเริ่มต้น 5 — ต้องการ ≥4 ปีเพื่อให้ MA200 สัปดาห์มีค่า)
        weeks_shown: จำนวนสัปดาห์ที่แสดงบนกราฟ (ค่าเริ่มต้น 160 ≈ 3 ปี)
        levels: ราคาที่ต้องการขีดเส้นประกำกับ เช่น จุด stop loss [70, 66]

    Returns:
        ภาพกราฟ PNG พร้อมสรุปตัวเลขสำคัญเป็นข้อความ
    """
    daily = _fetch_daily(symbol, years)
    weekly = to_weekly(daily)
    png = render_weekly_chart(weekly, symbol, levels=levels, weeks_shown=weeks_shown)
    return [
        _image_block(png),
        _summary(weekly, symbol),
    ]


@mcp.tool()
def weekly_table(symbol: str, weeks: int = 30) -> str:
    """คืนตารางราคารายสัปดาห์เป็นข้อความ (OHLCV + MA) สำหรับอ้างอิงตัวเลขแม่น ๆ

    ใช้คู่กับ weekly_chart เมื่อต้องการตัวเลขจริงแทนการอ่านค่าจากภาพ

    Args:
        symbol: ชื่อย่อหุ้น เช่น TOP
        weeks: จำนวนสัปดาห์ล่าสุดที่ต้องการ (ค่าเริ่มต้น 30)
    """
    daily = _fetch_daily(symbol, 5)
    df = to_weekly(daily)
    for n in MA_WEEKS:
        df[f"MA{n}"] = df["Close"].rolling(n).mean()
    out = df.tail(weeks).round(2)
    out.index = out.index.strftime("%Y-%m-%d")
    return f"{symbol.upper()} — weekly OHLCV\n\n{out.to_string()}"


@mcp.tool()
def compare_closes(symbols: list[str], weeks: int = 12) -> str:
    """เทียบราคาปิดรายสัปดาห์ของหลายตัวในตารางเดียว — ใช้ดูว่าตัวไหนนำ/ตามกลุ่ม

    Args:
        symbols: รายชื่อหุ้น เช่น ["TOP", "KKP", "OR"]
        weeks: จำนวนสัปดาห์ล่าสุด (ค่าเริ่มต้น 12)
    """
    cols = {}
    errors = []
    for s in symbols:
        try:
            cols[s.upper()] = to_weekly(_fetch_daily(s, 2))["Close"]
        except Exception as e:  # รายตัวพังไม่ควรทำให้ทั้งคำสั่งพัง
            errors.append(f"{s}: {e}")
    if not cols:
        return "ดึงข้อมูลไม่สำเร็จทุกตัว\n" + "\n".join(errors)

    table = pd.DataFrame(cols).tail(weeks).round(2)
    table.index = table.index.strftime("%Y-%m-%d")
    pct = ((table.iloc[-1] / table.iloc[0] - 1) * 100).round(2)

    body = [
        f"ราคาปิดรายสัปดาห์ ({weeks} สัปดาห์ล่าสุด)",
        "",
        table.to_string(),
        "",
        "เปลี่ยนแปลงรวมช่วงนี้ (%):",
        pct.to_string(),
    ]
    if errors:
        body += ["", "ดึงไม่สำเร็จ:"] + errors
    return "\n".join(body)


def _run_http(host: str, port: int, token: str | None, url_token: str | None) -> None:
    """รันเป็น HTTP server

    มี 2 วิธีป้องกัน เลือกใช้ตามว่า client ส่งอะไรได้:

    url_token (แนะนำ) — ความลับอยู่ใน URL: https://host/<url_token>/mcp
        สำหรับ client ที่กรอกได้แค่ URL อย่างเดียว เช่นหน้า Add custom connector
        ของ Claude ที่มีแค่ช่อง Name กับ URL ไม่มีที่ใส่ header
    token — bearer token ใน header Authorization
        สำหรับ client ที่ส่ง header เองได้ เช่น curl หรือสคริปต์

    เซิร์ฟเวอร์นี้อ่านข้อมูลราคาสาธารณะแล้ววาดกราฟอย่างเดียว ไม่มีคำสั่งเขียน
    ความลับจึงมีไว้กันการถูกยิงรัวจนโดนจำกัดโควตา มากกว่ากันข้อมูลรั่ว
    """
    import uvicorn
    from mcp.server.transport_security import TransportSecuritySettings
    from starlette.applications import Starlette
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.responses import JSONResponse
    from starlette.routing import Mount, Route

    # MCP SDK เปิด DNS rebinding protection ไว้โดยค่าเริ่มต้น และ allowed_hosts ว่าง
    # = ปฏิเสธทุก Host ที่ไม่ใช่ localhost ด้วย 421 Misdirected Request
    # เบื้องหลัง reverse proxy ของผู้ให้บริการ Host จะเป็นโดเมนจริง จึงต้องบอกให้รู้จัก
    allowed = [h.strip() for h in (os.environ.get("THAI_CHART_ALLOWED_HOSTS") or "").split(",") if h.strip()]
    if allowed:
        security = TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=allowed,
            allowed_origins=[f"https://{h}" for h in allowed] + [f"http://{h}" for h in allowed],
        )
        print(f"[security] จำกัด Host ไว้ที่: {', '.join(allowed)}", flush=True)
    else:
        # DNS rebinding protection มีไว้กันหน้าเว็บในเบราว์เซอร์ยิงเซิร์ฟเวอร์ที่ผูกกับ localhost
        # เซิร์ฟเวอร์สาธารณะหลัง HTTPS ไม่ได้อยู่ในสถานการณ์นั้น และของจริงที่ป้องกันเราคือ
        # ความลับใน URL — คนที่ไม่รู้ path ก็เรียกไม่ได้อยู่ดี ไม่ว่า Host จะเป็นอะไร
        security = TransportSecuritySettings(enable_dns_rebinding_protection=False)
        print(
            "[security] ปิด DNS rebinding protection (ยอมรับทุก Host)\n"
            "           ถ้าต้องการจำกัด ตั้ง THAI_CHART_ALLOWED_HOSTS=yourhost.onrender.com",
            flush=True,
        )

    inner = mcp.streamable_http_app(transport_security=security)

    # จุดตรวจสุขภาพสำหรับผู้ให้บริการโฮสต์ (Render ฯลฯ) — ต้องเปิดโล่งและอยู่ที่ราก
    # ถ้าเอา path ที่ต้องมีความลับไปเป็น health check ผู้ให้บริการจะเห็น 401/404
    # แล้วคิดว่าเซิร์ฟเวอร์ตาย → รีสตาร์ตวนไม่จบ
    async def health(_request):
        return JSONResponse({"status": "ok", "server": "thai-chart"})

    if url_token:
        # ซ่อน MCP ไว้ใต้ path ลับ — ใครไม่รู้ path ก็ได้ 404 ธรรมดา
        app = Starlette(
            routes=[
                Route("/health", health, methods=["GET"]),
                Mount(f"/{url_token}", app=inner),
            ],
            lifespan=lambda _app: inner.router.lifespan_context(inner),
        )
        shown = url_token[:4] + "…" + url_token[-2:] if len(url_token) > 8 else "…"
        print(f"[auth] ใช้ token ใน URL (ขึ้นต้น {shown})", flush=True)
        print(f"[serve] http://{host}:{port}/{url_token}/mcp", flush=True)
    else:
        app = inner
        app.router.routes.append(Route("/health", health, methods=["GET"]))

        if token:
            class BearerAuth(BaseHTTPMiddleware):
                async def dispatch(self, request, call_next):
                    if request.url.path in ("/health", "/healthz"):
                        return await call_next(request)
                    header = request.headers.get("authorization", "")
                    supplied = header[7:] if header.lower().startswith("bearer ") else ""
                    # เทียบแบบ constant-time กัน timing attack
                    import hmac
                    if not hmac.compare_digest(supplied, token):
                        return JSONResponse({"error": "unauthorized"}, status_code=401)
                    return await call_next(request)

            app.add_middleware(BearerAuth)
            print("[auth] ตรวจ bearer token ใน header", flush=True)
        else:
            print(
                "[auth] ⚠️  ไม่ได้ตั้งความลับใด ๆ — ใครก็เรียกได้\n"
                "        ตั้งด้วย THAI_CHART_URL_TOKEN (แนะนำ) หรือ THAI_CHART_TOKEN",
                flush=True,
            )
        print(f"[serve] http://{host}:{port}/mcp", flush=True)

    uvicorn.run(app, host=host, port=port, log_level="info")


def main() -> None:
    p = argparse.ArgumentParser(description="thai-chart MCP server")
    p.add_argument("--http", action="store_true", help="รันเป็น HTTP server แทน stdio")
    p.add_argument("--port", type=int, default=int(os.environ.get("PORT", 8000)))
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument(
        "--token",
        default=os.environ.get("THAI_CHART_TOKEN"),
        help="bearer token ใน header Authorization (หรือ env THAI_CHART_TOKEN)",
    )
    p.add_argument(
        "--url-token",
        default=os.environ.get("THAI_CHART_URL_TOKEN"),
        help="ความลับใน URL: /<url-token>/mcp — ใช้กับ client ที่กรอกได้แค่ URL "
        "(หรือ env THAI_CHART_URL_TOKEN) มีผลเหนือ --token",
    )
    args = p.parse_args()

    if args.http:
        _run_http(args.host, args.port, args.token, args.url_token)
    else:
        mcp.run()  # stdio — สำหรับ Claude Desktop บนเครื่องตัวเอง


if __name__ == "__main__":
    main()
