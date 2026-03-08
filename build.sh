#!/usr/bin/env bash
# Exit on error
set -o errexit

# Install Python dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Download and install FFmpeg static build
wget https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz
tar -xf ffmpeg-release-amd64-static.tar.xz
mkdir -p /opt/render/project/bin
mv ffmpeg-*-static/ffmpeg /opt/render/project/bin/
mv ffmpeg-*-static/ffprobe /opt/render/project/bin/
chmod +x /opt/render/project/bin/ffmpeg
chmod +x /opt/render/project/bin/ffprobe

echo "Build successful and FFmpeg installed!"
