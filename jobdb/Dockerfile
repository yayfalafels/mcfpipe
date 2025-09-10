# jobdb/Dockerfile
FROM public.ecr.aws/lambda/python:3.12
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# install dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# copy working directory
COPY jobdb/ .

# point to the entry point
CMD ["handler.lambda_handler"]