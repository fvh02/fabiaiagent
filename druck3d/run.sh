#!/bin/sh
echo "[3d-druck] Starte ..."
cd /app
exec /opt/venv/bin/python /app/server.py
