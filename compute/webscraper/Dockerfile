FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install OS-level deps (optional)
RUN apt-get update && apt-get install -y curl unzip chromium-driver chromium

# Copy app source code
COPY . /app

# Install Python deps
RUN pip install --no-cache-dir -r requirements.txt

# Entry point allows task selection
ENTRYPOINT ["python", "main.py"]