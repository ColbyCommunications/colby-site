#!/bin/bash

# Target URL
URL="https://rf26.colby.edu/"

if [ "$1" == "desktop" ]; then
  echo "Starting Desktop Audit for $URL"
  lighthouse "$URL" \
    --preset=desktop \
    --chrome-flags="--headless --incognito" \
    --view
    
elif [ "$1" == "mobile" ]; then
  echo "Starting Mobile Audit for $URL"
  lighthouse "$URL" \
    --form-factor=mobile \
    --throttling-method=simulate \
    --chrome-flags="--headless --incognito" \
    --view
    
else
  echo "Error: Must specify 'desktop' or 'mobile'."
  echo "Usage: npm run audit:desktop OR npm run audit:mobile"
  exit 1
fi