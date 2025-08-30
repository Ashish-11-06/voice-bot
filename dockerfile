# Base image
FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set work directory
WORKDIR /app

# Install system dependencies (adjust if you use MySQL/Postgres/aiortc)
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    libmariadb-dev \
    pkg-config \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project code
COPY . .

# Expose Daphne port
EXPOSE 8001

# Command to run your socketio server with Daphne
CMD ["daphne", "-b", "0.0.0.0", "-p", "8001", "chatbot_ws.socketio_server:app"]
