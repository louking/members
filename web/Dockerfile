ARG NGINX_VER
ARG PHPMYADMIN_VER
# COPY --from doesn't expand build args, but FROM does, so pull phpmyadmin in as a named stage
# see https://github.com/phpmyadmin/docker/issues/284#issuecomment-625468269
FROM phpmyadmin:${PHPMYADMIN_VER}-fpm AS phpmyadmin

FROM nginx:${NGINX_VER}-alpine
COPY nginx.conf /etc/nginx/nginx.conf
COPY index.html /usr/share/nginx/html/index.html
COPY --from=phpmyadmin /var/www/html /usr/share/nginx/html
