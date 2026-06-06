FROM node:22-alpine

WORKDIR /app

COPY package*.json ./
RUN npm ci --omit=dev

COPY src ./src

# /data is the HF Spaces persistent storage mount point (enable in Space Settings)
# Falls back to /app/data for local dev (SPACE_ID not set)
RUN mkdir -p /data /app/data

ENV NODE_ENV=production
# HuggingFace Spaces requires port 7860
EXPOSE 7860

CMD ["node", "src/index.js"]
