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

# stage runtime helpers
COPY import.py /app/import.py
COPY import_run_tests.sh /app/import_run_tests.sh
RUN chmod +x /app/import_run_tests.sh

# default entry: import tests at runtime, then run pytest on tests/
CMD ["sh","-lc","/app/import_run_tests.sh"]