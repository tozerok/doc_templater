FROM python:3.9.13-slim

ARG PYPI_PASSWORD
ARG PYPI_USERNAME
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends libmagic1 && rm -rf /var/lib/apt/lists/*

COPY docker/requirements.txt /app/

RUN pip3 install --no-cache-dir --upgrade -r requirements.txt

COPY src/static /app/static
COPY src/templates /app/templates
COPY src/main.py /app/src/

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
