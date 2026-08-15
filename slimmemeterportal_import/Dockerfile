ARG BUILD_FROM
ARG BUILD_VERSION
ARG BUILD_ARCH
FROM ${BUILD_FROM}

LABEL \
  io.hass.version="${BUILD_VERSION}" \
  io.hass.type="app" \
  io.hass.arch="${BUILD_ARCH}"

RUN apk add --no-cache ca-certificates tzdata py3-pip git openssh-client \
    && /usr/local/bin/python3 -m pip install --no-cache-dir --break-system-packages "reportlab>=4,<5" "pypdf>=5,<7" "xlsxwriter>=3.2,<4" \
    && /usr/local/bin/python3 -c "import reportlab, pypdf, xlsxwriter; print('report and xlsx runtime ok')" 

WORKDIR /app
COPY rootfs/app/ /app/
COPY run.sh /run.sh
RUN chmod 0755 /run.sh

ENV PYTHONUNBUFFERED=1 TZ=Europe/Amsterdam
EXPOSE 8099
CMD ["/run.sh"]
