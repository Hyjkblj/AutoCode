FROM python:3.11-slim
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY python-agent/requirements /app/requirements
RUN pip install --no-cache-dir -r /app/requirements/runtime.txt

COPY python-agent /app

ENTRYPOINT ["python", "main.py"]
