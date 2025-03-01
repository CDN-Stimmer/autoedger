#!/bin/bash

# Script to copy MP3 files from src/audio to src/data/audio that don't already exist in the destination
# This version handles all case variations of MP3 extensions

SRC_DIR="/tmp/anonymous-repo/src/audio"
DEST_DIR="/tmp/anonymous-repo/src/data/audio"

# Create destination directory if it doesn't exist
mkdir -p "$DEST_DIR"

# Find all MP3 files in the source directory (excluding the 000000faves subdirectory)
# Using case-insensitive pattern matching for extensions
find "$SRC_DIR" -maxdepth 1 -type f \( -iname "*.mp3" -o -iname "*.Mp3" -o -iname "*.mP3" -o -iname "*.MP3" \) | while read src_file; do
    filename=$(basename "$src_file")
    dest_file="$DEST_DIR/$filename"
    
    # Check if any file with the same name (ignoring case) exists in destination
    if ! find "$DEST_DIR" -maxdepth 1 -type f -iname "$filename" | grep -q .; then
        echo "Copying $filename to $DEST_DIR"
        cp "$src_file" "$dest_file"
    else
        echo "Skipping $filename (already exists in destination)"
    fi
done

echo "Copy operation completed." 