FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN python scripts/forecast_engine.py
EXPOSE 8080
CMD ["python", "src/server.py"]
