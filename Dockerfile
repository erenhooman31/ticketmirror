FROM python:3.12-slim

ARG INSTALL_TRANSLATION_MODELS=false

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements-translation.txt ./
RUN pip install --upgrade pip \
    && pip install -r requirements.txt \
    && if [ "$INSTALL_TRANSLATION_MODELS" = "true" ]; then \
        pip install -r requirements-translation.txt; \
    fi

COPY . .

RUN if [ "$INSTALL_TRANSLATION_MODELS" = "true" ]; then \
        python manage.py install_translation_models --from-code ru --to-code en; \
    fi

EXPOSE 8000

CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000"]
