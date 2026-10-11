FROM ubuntu:24.04

# OrcaSlicer (https://github.com/OrcaSlicer/OrcaSlicer) slices the models on the command line.
ARG ORCA_VERSION=2.3.2
ENV DEBIAN_FRONTEND=noninteractive LC_ALL=C.UTF-8 PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates curl python3 python3-venv \
        libgtk-3-0t64 libwebkit2gtk-4.1-0 libsoup-3.0-0 libsecret-1-0 libmspack0t64 \
        libegl1 libgl1 libopengl0 libglu1-mesa libwayland-server0 \
        libgstreamer1.0-0 libgstreamer-plugins-base1.0-0 libgstreamer-gl1.0-0 \
        libsm6 libice6 libx11-6 libx11-xcb1 libxext6 libxi6 libxinerama1 libxrandr2 libxcursor1 \
        libxcomposite1 libxdamage1 libxfixes3 libxrender1 libxkbcommon0 libepoxy0 libgbm1 libdrm2 \
        libfontconfig1 libfreetype6 libdbus-1-3 libglib2.0-0t64 libunwind8 libmanette-0.2-0 \
    && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL -o /tmp/orca.AppImage \
        "https://github.com/OrcaSlicer/OrcaSlicer/releases/download/v${ORCA_VERSION}/OrcaSlicer_Linux_AppImage_Ubuntu2404_V${ORCA_VERSION}.AppImage" \
    && chmod +x /tmp/orca.AppImage \
    && cd /opt && /tmp/orca.AppImage --appimage-extract >/dev/null \
    && mv /opt/squashfs-root /opt/orca \
    && rm /tmp/orca.AppImage \
    && /opt/orca/AppRun --help >/dev/null

COPY requirements.txt /tmp/requirements.txt
RUN python3 -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir -r /tmp/requirements.txt

COPY app /app
COPY run.sh /run.sh
RUN chmod a+x /run.sh

CMD [ "/run.sh" ]
