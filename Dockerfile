# Лёгкий официальный образ
FROM python:3.11-slim

# Обновим pip и установим зависимости
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    LANG=C.UTF-8

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Кладём код и PDF внутрь образа (или смонтируй томом при запуске)
COPY bot.py ./
COPY "Гайд по задачам АНОД 1.pdf" ./

# Никаких портов открывать не нужно (бот — исходящие соединения)
CMD ["python", "bot.py"]
