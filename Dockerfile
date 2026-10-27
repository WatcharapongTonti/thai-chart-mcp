FROM python:3.12-slim

# fonts-dejavu-core — matplotlib ต้องมีฟอนต์ ไม่งั้นข้อความบนกราฟหาย
RUN apt-get update \
 && apt-get install -y --no-install-recommends fonts-dejavu-core \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# คัดลอก requirements ก่อนโค้ด เพื่อให้ layer ของ pip ถูก cache ไว้
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py .

ENV MPLBACKEND=Agg \
    PORT=8000 \
    PYTHONUNBUFFERED=1

EXPOSE 8000

# host 0.0.0.0 ที่นี่ปลอดภัย เพราะเป็นภายใน container
# ตัวที่รับจากอินเทอร์เน็ตคือ reverse proxy ของผู้ให้บริการ
# THAI_CHART_TOKEN ต้องตั้งเป็น environment variable เสมอ — ห้ามใส่ในโค้ด
CMD ["sh", "-c", "python server.py --http --host 0.0.0.0 --port ${PORT}"]
