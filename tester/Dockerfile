# tester/Dockerfile
FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1  

WORKDIR /app

# install dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# create logs dir
RUN mkdir -p /var/log

# copy working directory
COPY . .

# run pytest tests.py. exits container non‑zero if tests fail.
CMD ["sh","-lc","set -o pipefail; pytest -q tests.py 2>&1 | tee /var/log/tests.log"]