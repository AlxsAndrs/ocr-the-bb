#!/bin/bash
set -euo pipefail

MOUNT_POINT=/mnt/smb
INPUT_DIR="$MOUNT_POINT/input"
PROCESSING_DIR="$MOUNT_POINT/processing"
OUTPUT_DIR="$MOUNT_POINT/output"
DONE_DIR="$MOUNT_POINT/done"
FAILED_DIR="$MOUNT_POINT/failed"
LANGUAGES="${OCR_LANGUAGES:-eng+fra}"

for d in "$INPUT_DIR" "$PROCESSING_DIR" "$OUTPUT_DIR" "$DONE_DIR" "$FAILED_DIR"; do
	mkdir -p "$d"
done

echo "Watching $INPUT_DIR for new files..."

inotifywait -m -e close_write -e moved_to --format '%f' "$INPUT_DIR" | while read -r FILENAME; do
	SRC="$INPUT_DIR/$FILENAME"

	if [[ ! "$FILENAME" =~ \.pdf$ ]]; then
		echo "Skipping non-PDF file: $FILENAME"
		continue
	fi

	echo "New file detected: $FILENAME"

	PROC_PATH="$PROCESSING_DIR/$FILENAME"
	mv "$SRC" "$PROC_PATH"

	OUT_PATH="$OUTPUT_DIR/$FILENAME"

	if ocrmypdf --language "$LANGUAGES" "$PROC_PATH" "$OUT_PATH"; then
		echo "OCR succeeded: $FILENAME"
		mv "$PROC_PATH" "$DONE_DIR/$FILENAME"
	else
		echo "OCR failed: $FILENAME"
		mv "$PROC_PATH" "$FAILED_DIR/$FILENAME"
	fi
done
