FROM node:22-alpine

WORKDIR /app

COPY package*.json ./
RUN npm ci --omit=dev

COPY src ./src

# Budget + metrics persistence (mount a HF persistent disk here if available)
RUN mkdir -p /app/data
VOLUME ["/app/data"]

ENV NODE_ENV=production
# HuggingFace Spaces requires port 7860
EXPOSE 7860

CMD ["node", "src/index.js"]
