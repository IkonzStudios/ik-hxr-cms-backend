#!/bin/bash

echo "Creating Lambda layers using Docker for correct architecture compatibility..."

# Create layers directory structure
mkdir -p src/layers/auth-dependencies/python
mkdir -p src/layers/common-dependencies/python

# Clean existing packages
rm -rf src/layers/auth-dependencies/python/*
rm -rf src/layers/common-dependencies/python/*

# Build auth dependencies layer using Docker with x86_64 platform
echo "Building auth dependencies layer with Docker (x86_64)..."
docker run --rm \
  --platform linux/amd64 \
  --entrypoint="" \
  -v $(pwd):/workspace \
  -w /workspace \
  public.ecr.aws/lambda/python:3.13 \
  pip install PyJWT==2.8.0 cryptography==41.0.7 -t src/layers/auth-dependencies/python

# Build common dependencies layer using Docker with x86_64 platform
echo "Building common dependencies layer with Docker (x86_64)..."
docker run --rm \
  --platform linux/amd64 \
  --entrypoint="" \
  -v $(pwd):/workspace \
  -w /workspace \
  public.ecr.aws/lambda/python:3.13 \
  pip install requests==2.31.0 -t src/layers/common-dependencies/python

# Create zip files
echo "Creating layer zip files..."
cd src/layers/auth-dependencies
rm -f auth-dependencies.zip
zip -r auth-dependencies.zip python/
cd ../common-dependencies
rm -f common-dependencies.zip
zip -r common-dependencies.zip python/
cd ../..

echo "Layers created successfully with correct architecture!"
echo "Auth dependencies: src/layers/auth-dependencies/auth-dependencies.zip"
echo "Common dependencies: src/layers/common-dependencies/common-dependencies.zip"

# Clean up any cache files
find src/layers -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
find src/layers -name "*.pyc" -delete 2>/dev/null || true

echo "✅ Lambda layers are ready for deployment!" 