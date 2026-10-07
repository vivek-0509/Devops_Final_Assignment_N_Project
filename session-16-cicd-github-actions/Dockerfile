FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir flask==3.1.3

COPY app ./app

ENV PORT=5000
EXPOSE 5000

CMD ["python", "-m", "app.server"]
