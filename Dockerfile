FROM python:3.12-slim

ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8
ENV PYTHONIOENCODING=utf-8

WORKDIR /app

# Зависимости отдельным слоем (кеширование)
COPY requirements.txt .
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir -r requirements.txt

# Код приложения
COPY . .

EXPOSE 8080

CMD ["python", "main.py", "--web"]
