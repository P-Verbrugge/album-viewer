FROM python:3.12-slim

WORKDIR /app

# ffmpeg is used to extract a still frame from video files for thumbnails.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .
COPY templates/ templates/
COPY static/ static/

ENV PHOTOS_ROOT=/photos
ENV CACHE_DIR=/cache
ENV THUMB_SIZE=400

EXPOSE 8080

CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "2", "--threads", "4", "app:app"]
