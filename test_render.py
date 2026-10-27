"""ทดสอบการวาดกราฟด้วยข้อมูลจำลอง — ไม่ต้องต่อเน็ต

รัน:  python3 test_render.py
ผล:  เขียนไฟล์ test_output.png และพิมพ์สรุปตัวเลข
"""

import numpy as np
import pandas as pd

from server import _summary, render_weekly_chart, to_weekly

rng = np.random.default_rng(7)

# สร้างราคารายวัน 5 ปี แบบ random walk ที่มีแนวโน้มขึ้นแล้วย่อ
n = 252 * 5
drift = np.concatenate([np.full(n - 120, 0.0012), np.full(120, -0.0022)])
close = 30 * np.exp(np.cumsum(drift + rng.normal(0, 0.016, n)))
idx = pd.bdate_range(end="2026-10-23", periods=n)

daily = pd.DataFrame(
    {
        "Open": close * (1 + rng.normal(0, 0.004, n)),
        "High": close * (1 + abs(rng.normal(0, 0.009, n))),
        "Low": close * (1 - abs(rng.normal(0, 0.009, n))),
        "Close": close,
        "Volume": rng.integers(5_000_000, 40_000_000, n).astype(float),
    },
    index=idx,
)

weekly = to_weekly(daily)
print(f"แท่งรายวัน {len(daily)} → แท่งรายสัปดาห์ {len(weekly)}")

assert len(weekly) > 200, "ข้อมูลไม่พอสำหรับ MA200 สัปดาห์"
assert list(weekly.columns) == ["Open", "High", "Low", "Close", "Volume"]
assert (weekly["High"] >= weekly["Low"]).all(), "High ต้องไม่ต่ำกว่า Low"

png = render_weekly_chart(weekly, "TEST", levels=[70.0, 66.0], weeks_shown=160)
assert png[:8] == b"\x89PNG\r\n\x1a\n", "ผลลัพธ์ไม่ใช่ไฟล์ PNG"

with open("test_output.png", "wb") as f:
    f.write(png)

print(f"วาดกราฟสำเร็จ: test_output.png ({len(png):,} bytes)")
print()
print(_summary(weekly, "TEST"))
