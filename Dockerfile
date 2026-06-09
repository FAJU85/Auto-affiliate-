FROM python:3.12-slim

WORKDIR /app

# Python dependencies
COPY api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code
COPY api ./api
COPY src/dashboard.html ./src/dashboard.html

# /data is the HF Spaces persistent storage mount point
RUN mkdir -p /data
VOLUME ["/data"]

ENV NODE_ENV=production
ENV DATA_DIR=/data
# HuggingFace Spaces requires port 7860
EXPOSE 7860

HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:7860/health').status==200 else 1)" || exit 1

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "7860", "--workers", "1"]
