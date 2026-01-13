# Build stage
FROM node:20-alpine AS builder

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci

# Copy source files
COPY . .

# Build the app
RUN npm run build

# Production stage
FROM nginx:alpine

# Copy custom nginx config
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy built files
COPY --from=builder /app/dist /usr/share/nginx/html

# Create data directory for mounting
RUN mkdir -p /usr/share/nginx/html/data/storage /usr/share/nginx/html/data/info

# Expose port
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
