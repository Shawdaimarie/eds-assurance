FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 EDS_DB_PATH=/data/assurance.db
WORKDIR /app
COPY requirements.lock requirements-build.lock pyproject.toml ./
COPY src ./src
RUN python -m pip install --no-cache-dir -r requirements.lock -r requirements-build.lock \
    && python -m pip install --no-cache-dir --no-deps --no-build-isolation . \
    && groupadd --gid 10001 eds \
    && useradd --uid 10001 --gid eds --no-create-home eds \
    && mkdir /data && chown eds:eds /data
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/readyz', timeout=2)"
CMD ["uvicorn", "eds_assurance.api:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--limit-concurrency", "32", "--timeout-keep-alive", "5", "--no-server-header"]
