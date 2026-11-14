# ERiC braucht glibc (Debian) – darum nicht das Alpine-Basisbild von Home Assistant
FROM python:3.12-slim-bookworm
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates libstdc++6 \
 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY run.py /app/run.py
CMD ["python3", "-u", "/app/run.py"]
