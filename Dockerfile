FROM python:3.12-alpine
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN chmod +x /app/entrypoint.sh && mkdir -p /data
ENV SQLITE_PATH=/data/db.sqlite3 DJANGO_DEBUG=false
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD wget -qO- http://127.0.0.1:8000/health/ || exit 1
ENTRYPOINT ["/app/entrypoint.sh"]
