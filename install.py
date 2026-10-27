#!/usr/bin/env python3
"""ติดตั้ง thai-chart-mcp แบบอัตโนมัติ

รัน:  python3 install.py

สคริปต์นี้จะ:
  1. สร้าง virtual environment (.venv) ในโฟลเดอร์นี้
  2. ติดตั้ง library ที่ต้องใช้
  3. ทดสอบว่าวาดกราฟได้จริง
  4. เพิ่ม thai-chart เข้า config ของ Claude Desktop (รวมกับของเดิม ไม่ลบทิ้ง)

ปลอดภัย: สำรอง config เดิมไว้ก่อนเสมอ และแก้เฉพาะคีย์ "thai-chart"
รันซ้ำได้ ไม่พัง

ตัวเลือก:
  --no-config   ติดตั้งอย่างเดียว ไม่แตะ config ของ Claude
  --print-config  แสดง config ที่ต้องใส่ แล้วจบ (เอาไว้ใส่เองด้วยมือ)
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
VENV = HERE / ".venv"
SERVER = HERE / "server.py"
KEY = "thai-chart"


def say(msg: str) -> None:
    print(msg, flush=True)


def step(n: int, msg: str) -> None:
    say(f"\n[{n}/4] {msg}")


def venv_python() -> Path:
    if platform.system() == "Windows":
        return VENV / "Scripts" / "python.exe"
    return VENV / "bin" / "python"


def claude_config_path() -> Path | None:
    """หา config ของ Claude Desktop ตามระบบปฏิบัติการ"""
    system = platform.system()
    if system == "Darwin":
        return Path.home() / "Library/Application Support/Claude/claude_desktop_config.json"
    if system == "Windows":
        appdata = os.environ.get("APPDATA")
        return Path(appdata) / "Claude" / "claude_desktop_config.json" if appdata else None
    if system == "Linux":
        base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
        return Path(base) / "Claude" / "claude_desktop_config.json"
    return None


def run(cmd: list[str], what: str) -> None:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        say(f"  ✗ {what} ไม่สำเร็จ")
        tail = (result.stderr or result.stdout or "").strip().splitlines()[-12:]
        for line in tail:
            say(f"    {line}")
        sys.exit(1)


def server_entry() -> dict:
    return {"command": str(venv_python()), "args": [str(SERVER)]}


def create_venv() -> None:
    step(1, "สร้าง virtual environment")
    if venv_python().exists():
        say(f"  • มีอยู่แล้ว: {VENV}")
        return
    run([sys.executable, "-m", "venv", str(VENV)], "สร้าง venv")
    say(f"  ✓ {VENV}")


def install_deps() -> None:
    step(2, "ติดตั้ง library (อาจใช้เวลาสัก 1-2 นาที)")
    py = str(venv_python())
    run([py, "-m", "pip", "install", "--upgrade", "pip", "-q"], "อัปเกรด pip")
    run([py, "-m", "pip", "install", "-r", str(HERE / "requirements.txt"), "-q"], "ติดตั้ง library")
    say("  ✓ ติดตั้งครบ")


def smoke_test() -> None:
    step(3, "ทดสอบว่าวาดกราฟได้")
    result = subprocess.run(
        [str(venv_python()), str(HERE / "test_render.py")],
        capture_output=True,
        text=True,
        cwd=str(HERE),
    )
    if result.returncode != 0:
        say("  ✗ ทดสอบไม่ผ่าน")
        for line in (result.stderr or "").strip().splitlines()[-12:]:
            say(f"    {line}")
        sys.exit(1)
    out = HERE / "test_output.png"
    say(f"  ✓ วาดกราฟได้ → {out}")
    say("    (เปิดดูได้เลย ถ้าเห็นแท่งเทียน + เส้น MA 3 เส้น + วอลุ่ม = ใช้ได้)")


def write_config() -> None:
    step(4, "เพิ่มเข้า config ของ Claude Desktop")
    cfg = claude_config_path()
    if cfg is None:
        say(f"  ! ไม่รู้จักระบบปฏิบัติการ {platform.system()} — ใส่ config เองตาม README")
        return

    existing: dict = {}
    if cfg.exists():
        try:
            existing = json.loads(cfg.read_text(encoding="utf-8")) or {}
        except json.JSONDecodeError:
            say(f"  ✗ config เดิมอ่านไม่ได้ (JSON ผิดรูปแบบ): {cfg}")
            say("    แก้ไฟล์นั้นให้ถูกก่อน หรือรันใหม่ด้วย --print-config แล้วใส่เอง")
            sys.exit(1)
        backup = cfg.with_suffix(f".backup-{datetime.now():%Y%m%d-%H%M%S}.json")
        shutil.copy2(cfg, backup)
        say(f"  • สำรองของเดิมไว้ที่ {backup.name}")
    else:
        cfg.parent.mkdir(parents=True, exist_ok=True)
        say(f"  • ยังไม่มี config เดิม จะสร้างใหม่ที่ {cfg}")

    servers = existing.setdefault("mcpServers", {})
    others = [k for k in servers if k != KEY]
    action = "อัปเดต" if KEY in servers else "เพิ่ม"
    servers[KEY] = server_entry()

    cfg.write_text(json.dumps(existing, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    say(f"  ✓ {action} '{KEY}' แล้ว")
    if others:
        say(f"  • MCP server เดิมอยู่ครบ: {', '.join(others)}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-config", action="store_true", help="ไม่แตะ config ของ Claude")
    ap.add_argument("--print-config", action="store_true", help="แสดง config แล้วจบ")
    args = ap.parse_args()

    if args.print_config:
        print(json.dumps({"mcpServers": {KEY: server_entry()}}, indent=2))
        return

    if sys.version_info < (3, 10):
        say(f"✗ ต้องใช้ Python 3.10 ขึ้นไป (ตอนนี้ {platform.python_version()})")
        sys.exit(1)
    if not SERVER.exists():
        say(f"✗ ไม่พบ server.py ที่ {SERVER} — รันสคริปต์นี้จากในโฟลเดอร์ thai-chart-mcp")
        sys.exit(1)

    say(f"ติดตั้ง thai-chart-mcp  ({platform.system()}, Python {platform.python_version()})")
    say(f"โฟลเดอร์: {HERE}")

    create_venv()
    install_deps()
    smoke_test()
    if args.no_config:
        say("\n[4/4] ข้ามการแก้ config ตามที่สั่ง (--no-config)")
    else:
        write_config()

    say("\n" + "=" * 56)
    say("เสร็จแล้ว")
    say("=" * 56)
    say("\nขั้นต่อไป: ปิด Claude Desktop แล้วเปิดใหม่ (ต้องปิดสนิท ไม่ใช่แค่ปิดหน้าต่าง)")
    say("จากนั้นลองพิมพ์:  วาดกราฟรายสัปดาห์ของ TOP พร้อมเส้น stop ที่ 70 กับ 66")
    say("\nถ้าไม่ขึ้น: ดูหัวข้อ 'ถ้าไม่ขึ้นใน Claude' ใน README.md")


if __name__ == "__main__":
    main()
