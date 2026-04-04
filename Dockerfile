FROM python:3.11-slim

# 1. Install system dependencies (added curl here)
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    unzip \
    libzip-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 2. Download KataGo (Eigen CPU version for broad compatibility)
RUN wget -q https://github.com/lightvector/KataGo/releases/download/v1.14.1/katago-v1.14.1-eigen-linux-x64.zip -O katago.zip \
    && unzip katago.zip \
    && chmod +x katago \
    && rm katago.zip

# 3. Download a fast 15-block neural network model for KataGo 
# (Using curl and a User-Agent to bypass Cloudflare bot protection)
RUN curl -L -A "Mozilla/5.0 (Windows NT 10.0; Win64; x64)" -o model.bin.gz https://media.katagotraining.org/uploaded/networks/models/kata1/kata1-b15c192-s1672170752-d466197061.bin.gz

# 4. Create a basic GTP configuration for KataGo to restrict threads and logging
RUN echo "logDir = gtp_logs\n\
logSearchInfo = false\n\
numSearchThreads = 4\n" > gtp_config.cfg

# 5. Copy Python requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 6. Copy backend and frontend files
COPY app.py .
COPY index.html .

EXPOSE 8000

# 7. Start the FastAPI server
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]