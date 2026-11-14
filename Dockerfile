FROM python:3.14-slim

WORKDIR /app

COPY pyproject.toml ./

RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

COPY src ./src
COPY scripts ./scripts
COPY README.md ./

RUN pip install --no-cache-dir .

COPY models ./models

ENV MODEL_PATH=/app/models/vortemis_ae.pt

EXPOSE 8501

CMD ["python", "-m", "vortemis.entrypoints.cli"]
