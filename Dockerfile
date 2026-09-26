FROM python:3.12.14-slim@sha256:2f17fc044b579bab302c2e8054d3a686e2cb9a83de48e70534b94cd8ebbe06a9

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml README.md LICENSE ./
COPY veeam_designer/ ./veeam_designer/
COPY ui/ ./ui/
COPY config.json profiles.json example-project.yml ./

RUN pip install . \
    && groupadd --gid 10001 veeam \
    && useradd --uid 10001 --gid veeam --no-create-home --home-dir /app --shell /usr/sbin/nologin veeam

USER 10001:10001

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3).read()"]

CMD ["veeam-designer-web", "--host", "0.0.0.0", "--port", "8000"]
