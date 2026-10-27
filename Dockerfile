FROM python:3.14-slim

WORKDIR /app

COPY pyproject.toml ./
COPY src ./src
COPY scripts ./scripts

RUN pip install --no-cache-dir .

CMD ["python", "-m", "vortemis.entrypoints.cli"]
