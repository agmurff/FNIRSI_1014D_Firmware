# Parameterised so the image can be built on a host that cannot reach the registry:
# point BASE at any python slim image already present locally.
ARG BASE=python:3.12-slim
FROM ${BASE}

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .
COPY static/ ./static/

EXPOSE 8080

# Single worker on purpose: the poller holds one MCP session to the scope, and the
# scope serialises access to a single serial port anyway. More workers would mean
# several pollers competing for it.
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]
