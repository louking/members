# adapted from https://stackoverflow.com/a/47960145/799921
ARG ALPINE_VER
FROM alpine:${ALPINE_VER}
COPY cronjobs /etc/crontabs/root

# we'll be doing mysqldump commands
RUN apk add --no-cache mysql-client

# use msmtp for sendmail, need volume with /etc/msmtprc defined
RUN apk add --no-cache msmtp && rm /usr/sbin/sendmail && ln -s /usr/bin/msmtp /usr/sbin/sendmail

# allow timezone setting
RUN apk add --no-cache tzdata
