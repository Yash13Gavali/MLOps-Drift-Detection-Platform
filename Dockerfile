FROM python:3.11.13-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 DATA_ROOT=/data
WORKDIR /app
COPY requirements.lock pyproject.toml ./
RUN pip install --no-cache-dir -r requirements.lock
COPY src ./src
COPY tests ./tests
RUN pip install --no-cache-dir --no-deps --no-build-isolation . \
    && useradd --uid 10001 --create-home platform \
    && mkdir /data && chown platform:platform /data
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/ready', timeout=3)"
ENTRYPOINT ["drift-platform"]
CMD ["serve"]

