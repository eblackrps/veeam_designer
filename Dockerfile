FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    CHROME_POLICY_MERGE_WORKSPACE_ROOT=/workspace

WORKDIR /app

COPY pyproject.toml README.md CHANGELOG.md CONTRIBUTING.md LICENSE MANIFEST.in SECURITY.md setup.py ./
COPY src ./src
COPY docs ./docs
COPY examples ./examples
COPY ui ./ui

RUN python -m pip install --upgrade pip \
    && python -m pip install .

RUN mkdir -p /workspace

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3)"

CMD ["chrome-policy-merge-web", "--host", "0.0.0.0", "--port", "8000"]
