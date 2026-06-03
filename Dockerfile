FROM node:22-alpine

WORKDIR /app

COPY package*.json ./
RUN npm ci --omit=dev

COPY src ./src

# Data directory for budget + metrics persistence
VOLUME ["/app/data"]

ENV NODE_ENV=production

CMD ["node", "src/index.js"]
