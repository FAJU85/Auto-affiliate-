FROM node:22-alpine

# Install Python + pip for FastAPI social OAuth backend
RUN apk add --no-cache python3 py3-pip py3-virtualenv

WORKDIR /app

# Node dependencies
COPY package*.json ./
RUN npm ci --omit=dev

# Python dependencies (isolated venv to avoid distutils conflicts)
COPY api/requirements.txt ./api/requirements.txt
RUN python3 -m venv /opt/venv && \
    /opt/venv/bin/pip install --no-cache-dir -r api/requirements.txt

ENV PATH="/opt/venv/bin:$PATH"

# Application code
COPY src ./src
COPY api ./api
COPY start.sh ./start.sh
RUN chmod +x start.sh

# /data is the HF Spaces persistent storage mount point (enable in Space Settings)
RUN mkdir -p /data /app/data

ENV NODE_ENV=production
ENV DATA_DIR=/data
# HuggingFace Spaces requires port 7860
EXPOSE 7860

HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
  CMD wget -qO- http://localhost:7860/health || exit 1

CMD ["./start.sh"]
