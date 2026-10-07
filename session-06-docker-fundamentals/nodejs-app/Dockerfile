# Node.js Hello World - Dockerfile
FROM node:24-alpine

WORKDIR /app

# Install dependencies first (better layer caching)
COPY package*.json ./
RUN npm install --omit=dev

# Copy application code
COPY server.js .

EXPOSE 3000

CMD ["npm", "start"]
