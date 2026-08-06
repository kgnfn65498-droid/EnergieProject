ARG BUILD_FROM
ARG BUILD_VERSION
ARG BUILD_ARCH
FROM ${BUILD_FROM}

LABEL \
  io.hass.version="${BUILD_VERSION}" \
  io.hass.type="app" \
  io.hass.arch="${BUILD_ARCH}"

RUN apk add --no-cache ca-certificates tzdata

WORKDIR /app
COPY rootfs/app/ /app/
COPY run.sh /run.sh
RUN chmod 0755 /run.sh

ENV PYTHONUNBUFFERED=1 TZ=Europe/Amsterdam
EXPOSE 8099
CMD ["/run.sh"]
