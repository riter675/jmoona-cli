# jmoona-cli — Docker Image
# Usage:
#   docker build -t jmoona .
#   docker run -it --rm \
#     -e DISPLAY=:0 \
#     -v /tmp/.X11-unix:/tmp/.X11-unix \
#     -v "$HOME/Downloads/jmoona:/root/Downloads/jmoona" \
#     jmoona

FROM python:3.12-slim

LABEL maintainer="jmoona-cli"
LABEL description="Films & séries en streaming depuis n'importe où"

# System deps: mpv, yt-dlp, Xvfb, Chromium
RUN apt-get update && apt-get install -y --no-install-recommends \
    mpv \
    yt-dlp \
    chromium \
    chromium-driver \
    xvfb \
    ffmpeg \
    git \
    curl \
    locales \
    && locale-gen fr_FR.UTF-8 \
    && rm -rf /var/lib/apt/lists/*

ENV LANG=fr_FR.UTF-8
ENV LANGUAGE=fr_FR:fr
ENV LC_ALL=fr_FR.UTF-8
ENV DISPLAY=:99
ENV PYTHONUNBUFFERED=1

# Install Python deps
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir -e .

# jmoona config dir
RUN mkdir -p /root/.config/jmoona

# Entrypoint: start Xvfb in background then launch jmoona
CMD ["bash", "-c", "Xvfb :99 -screen 0 1280x720x24 &>/dev/null & sleep 1 && jmoona"]
