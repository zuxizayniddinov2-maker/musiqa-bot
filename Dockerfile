FROM python:3.13-slim

# System updates and FFmpeg installation
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application files
COPY . .

# Directory for media
RUN mkdir -p downloads

# Port for Render Web Service
EXPOSE 8080

# Launch application
CMD ["python", "bot.py"]
