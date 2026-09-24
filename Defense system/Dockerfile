FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt --no-cache-dir
COPY . .
CMD ["streamlit", "run", "src/app.py", "--server.port", "8501", "--server.address", "0.0.0.0"]
