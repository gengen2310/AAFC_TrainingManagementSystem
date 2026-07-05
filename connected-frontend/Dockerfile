FROM nginx:1.27-alpine

# Copy static app and configuration
COPY index.html /usr/share/nginx/html/index.html
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

# Railway injects PORT at runtime (typically 8080)
EXPOSE 8080

ENTRYPOINT ["/docker-entrypoint.sh"]
