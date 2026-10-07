# Stage 1: install dependencies
FROM python:3.12-alpine AS builder
WORKDIR /install
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Stage 2: minimal Alpine runtime, non-root user.
# (python:3.12-slim/Debian carried 44 HIGH CVEs in util-linux at scan time; the Alpine base scanned clean.)
FROM python:3.12-alpine
RUN addgroup -S app && adduser -S -u 10001 -G app app
WORKDIR /app
COPY --from=builder /install /usr/local
COPY app ./app
USER app
ENV PORT=5001
EXPOSE 5001
CMD ["gunicorn", "-b", "0.0.0.0:5001", "-w", "2", "app.app:app"]
