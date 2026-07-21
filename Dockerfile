FROM python:3.12-slim

WORKDIR /app

# ffmpeg is used to extract a still frame from video files for thumbnails.
# Installed as a static binary (via a direct HTTPS download, using only
# Python's own standard library) instead of through apt-get, since Debian's
# package mirrors have proven unreliable on some networks — this only needs
# one host to be reachable rather than apt's whole mirror infrastructure.
RUN python3 -c "\
import platform, tarfile, os, glob, shutil, urllib.request; \
arch = 'arm64' if platform.machine() in ('aarch64', 'arm64') else 'amd64'; \
url = f'https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-{arch}-static.tar.xz'; \
urllib.request.urlretrieve(url, '/tmp/ffmpeg.tar.xz'); \
tarfile.open('/tmp/ffmpeg.tar.xz').extractall('/tmp/ffmpeg_extracted'); \
binpath = glob.glob('/tmp/ffmpeg_extracted/ffmpeg-*-static/ffmpeg')[0]; \
shutil.move(binpath, '/usr/local/bin/ffmpeg'); \
os.chmod('/usr/local/bin/ffmpeg', 0o755); \
shutil.rmtree('/tmp/ffmpeg_extracted'); \
os.remove('/tmp/ffmpeg.tar.xz') \
" \
    && ffmpeg -version

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .
COPY album_app/ album_app/
COPY templates/ templates/
COPY static/ static/

ENV PHOTOS_ROOT=/photos
ENV CACHE_DIR=/cache
ENV THUMB_SIZE=400

EXPOSE 8080

CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "2", "--threads", "4", "app:app"]
