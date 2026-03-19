FROM python:3.12-slim

WORKDIR /app

# Зависимости отдельным слоем (кеширование)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Код приложения
COPY . .

EXPOSE 8080

CMD ["python", "main.py", "--web"]
