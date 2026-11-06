FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN useradd --create-home app && chown -R app /app
USER app
# 1 processo + várias threads: a trava contra adoção duplicada vale por processo
CMD exec gunicorn --bind :${PORT:-8080} --workers 1 --threads 8 --timeout 60 app:app
