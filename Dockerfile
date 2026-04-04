FROM python:3.11-slim

# Install system dependencies (wget, unzip, and libraries KataGo might need)
RUN apt-get update && apt-get install -y \
    wget \
    unzip \
    libzip-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Download KataGo (Eigen CPU version for broad compatibility)
RUN wget -q https://github.com/lightvector/KataGo/releases/download/v1.14.1/katago-v1.14.1-eigen-linux-x64.zip -O katago.zip \
    && unzip katago.zip \
    && chmod +x katago \
    && rm katago.zip

# Download a fast 15-block neural network model for KataGo
RUN wget -q -O model.bin.gz https://katagotraining.org/api/networks/kata1-b15c192-s1672170752-d466197061/network_file

# Create a basic GTP configuration for KataGo to restrict threads and logging
RUN echo "logDir = gtp_logs\n\
logSearchInfo = false\n\
numSearchThreads = 4\n" > gtp_config.cfg

# Copy Python requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend and frontend files
COPY app.py .
COPY index.html .

EXPOSE 8000

# Start the FastAPI server
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]