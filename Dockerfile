FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml .
COPY veeam_designer/ ./veeam_designer/
COPY ui/ ./ui/
COPY config.json profiles.json example-project.yml ./

RUN pip install --no-cache-dir -e ".[web]"

EXPOSE 8000

CMD ["uvicorn", "ui.main:app", "--host", "0.0.0.0", "--port", "8000"]
