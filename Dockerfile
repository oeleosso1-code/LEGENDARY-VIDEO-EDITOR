FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg ca-certificates fontconfig fonts-noto-core && rm -rf /var/lib/apt/lists/*
WORKDIR /studio
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
RUN useradd -m studio && mkdir -p /studio/jobs && chown -R studio:studio /studio
USER studio
CMD ["python", "-m", "app.bot_pro"]
