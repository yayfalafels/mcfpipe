FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    wget unzip curl gnupg ca-certificates \
    chromium chromium-driver \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Set environment variable to let Selenium find Chromium
ENV PATH="/usr/lib/chromium/:$PATH"

# Install Python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy your source code
COPY . /mcfscrape
WORKDIR /mcfscrape

ENTRYPOINT ["python", "handler.py"]