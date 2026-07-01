FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
	ocrmypdf \
	tesseract-ocr-eng \
	tesseract-ocr-fra \
	cifs-utils \
	inotify-tools \
	&& rm -rf /var/lib/apt/lists/*

RUN mkdir -p /mnt/smb/input /mnt/smb/processing /mnt/smb/output /mnt/smb/done /mnt/smb/failed

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]