# Multi-stage Dockerfile for React TypeScript Frontend
# Optimized for production deployment with nginx

# Stage 1: Builder
FROM node:18-alpine as builder

# Set working directory
WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies with exact versions
RUN npm ci --only=production && \
    npm cache clean --force

# Copy all frontend source code
COPY . .

# Build production bundle
RUN npm run build

# Stage 2: Runtime (Nginx)
FROM nginx:alpine

# Install curl for health checks
RUN apk add --no-cache curl

# Remove default nginx config
RUN rm /etc/nginx/conf.d/default.conf

# Copy custom nginx configuration
COPY nginx.conf /etc/nginx/conf.d/

# Copy built static files from builder stage
COPY --from=builder /app/dist /usr/share/nginx/html

# Create non-root user for nginx (optional security enhancement)
RUN chown -R nginx:nginx /usr/share/nginx/html && \
    chmod -R 755 /usr/share/nginx/html

# Expose port 80
EXPOSE 80

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost/health || exit 1

# Run nginx in foreground
CMD ["nginx", "-g", "daemon off;"]