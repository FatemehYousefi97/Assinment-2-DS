FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv
COPY requirements.txt .
ARG PIP_INDEX_URL
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY config ./config
COPY db ./db
COPY scripts ./scripts
COPY tests ./tests
USER 10001
EXPOSE 8000
CMD ["uvicorn", "app.shard:app", "--host", "0.0.0.0", "--port", "8000"]

