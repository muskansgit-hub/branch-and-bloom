FROM python:3.12-slim
WORKDIR /app
# The app uses only the Python standard library, so there is nothing to pip install.
COPY server.py ./
COPY public ./public
RUN useradd --create-home bloom && mkdir /data && chown bloom /data
USER bloom
ENV BLOOM_HOST=0.0.0.0 \
    BLOOM_DB=/data/bloom.sqlite3 \
    PORT=8765
EXPOSE 8765
# Render sets PORT and RENDER_EXTERNAL_HOSTNAME automatically. Elsewhere, set
# BLOOM_PUBLIC_HOSTS yourself to the public hostname (for example demo.example.com).
CMD ["sh", "-c", "export BLOOM_PUBLIC_HOSTS=\"${BLOOM_PUBLIC_HOSTS:-$RENDER_EXTERNAL_HOSTNAME}\"; exec python server.py"]
