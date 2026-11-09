FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# libpango/libcairo: native rendering engine WeasyPrint uses to turn the
# client-facing report's HTML/CSS into PDF (reports/pdf.py; modern WeasyPrint
# decodes raster images itself, no libgdk-pixbuf needed). fonts-dejavu-core: a
# font actually installed in the image with full á/ã/ç coverage for PT-BR text -
# without it WeasyPrint falls back to tofu boxes since python:3.13-slim ships no fonts.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libpq-dev gcc netcat-openbsd \
        libpango-1.0-0 libpangocairo-1.0-0 libcairo2 \
        libffi-dev shared-mime-info fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

COPY docker/django/entrypoint.sh /entrypoint.sh
RUN sed -i 's/\r$//' /entrypoint.sh && chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
