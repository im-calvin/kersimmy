FROM python:3.13-slim

ARG READER_RELEASE

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    READER_DATA=/data \
    READER_RELEASE=${READER_RELEASE} \
    BACKUP_INTERVAL_SECONDS=900 \
    BACKUP_KEEP=96

WORKDIR /app
COPY tools/ tools/
COPY web/ web/
RUN chmod -R a+rX tools web \
    && python tools/build_web.py --without-current \
    && groupadd --gid 10001 reader \
    && useradd --uid 10001 --gid 10001 --no-create-home reader \
    && mkdir -p /data \
    && chown reader:reader /data

USER reader
VOLUME ["/data"]
EXPOSE 8888
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8888/api/status', timeout=3).close()"]
CMD ["python", "tools/reader_server.py", "--host", "0.0.0.0", "--port", "8888"]
