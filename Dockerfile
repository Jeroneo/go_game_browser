FROM python:3.11-slim-bullseye

# 1. Install system dependencies
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    unzip \
    libzip-dev \
    zlib1g-dev \
    libgomp1 \
    libssl1.1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 2. Fix the missing libzip.so.5 error
# KataGo expects libzip5, but Debian natively provides libzip4.
# We download the specific library from the Ubuntu 20.04 archives to satisfy KataGo.
RUN wget -q http://mirrors.kernel.org/ubuntu/pool/universe/libz/libzip/libzip5_1.5.1-0ubuntu1_amd64.deb \
    && apt-get update \
    && apt-get install -y ./libzip5_1.5.1-0ubuntu1_amd64.deb \
    && rm libzip5_1.5.1-0ubuntu1_amd64.deb \
    && rm -rf /var/lib/apt/lists/*

# 3. Download KataGo (Eigen CPU version)
RUN wget -q https://github.com/lightvector/KataGo/releases/download/v1.14.1/katago-v1.14.1-eigen-linux-x64.zip -O katago.zip \
    && unzip katago.zip \
    && chmod +x katago \
    && rm katago.zip

# 4. Download a fast 15-block neural network model for KataGo
RUN curl -L -A "Mozilla/5.0 (Windows NT 10.0; Win64; x64)" -o model.bin.gz https://media.katagotraining.org/uploaded/networks/models/kata1/kata1-b15c192-s1672170752-d466197061.bin.gz

# 5. Create a basic GTP configuration for KataGo
RUN echo "logSearchInfo = false\n\
numSearchThreads = 4\n" > gtp_config.cfg

# 6. Copy Python requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 7. Copy backend and frontend files
COPY app.py .
COPY index.html .

EXPOSE 8000

# 8. Start the FastAPI server
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]