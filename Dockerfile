FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md LICENSE ./
COPY veeam_designer/ ./veeam_designer/
COPY ui/ ./ui/
COPY config.json profiles.json example-project.yml ./

RUN pip install --no-cache-dir .

EXPOSE 8000

CMD ["veeam-designer-web", "--host", "0.0.0.0", "--port", "8000"]
