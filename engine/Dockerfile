FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY pyproject.toml ./
COPY marsad ./marsad
RUN pip install . && useradd --create-home marsad && mkdir -p /data && chown marsad /data
USER marsad
ENV MARSAD_STORAGE_DIR=/data
EXPOSE 8000
CMD ["uvicorn", "marsad.api.app:app_factory", "--factory", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
