FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=80
ENV FLASK_HOST=0.0.0.0
ENV FLASK_DEBUG=0

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 80

CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT:-80} wsgi:app"]
