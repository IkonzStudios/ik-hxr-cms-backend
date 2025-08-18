#!/bin/bash

# Create layers directory structure
mkdir -p src/layers/auth-dependencies/python
mkdir -p src/layers/common-dependencies/python

# Install auth-specific dependencies
echo "Installing auth dependencies..."
pip install PyJWT==2.8.0 cryptography==41.0.7 -t src/layers/auth-dependencies/python

# Install common dependencies
echo "Installing common dependencies..."
pip install requests==2.31.0 -t src/layers/common-dependencies/python

# Create zip files
echo "Creating layer zip files..."
cd src/layers/auth-dependencies
zip -r auth-dependencies.zip python/
cd ../common-dependencies
zip -r common-dependencies.zip python/
cd ../..

echo "Layers created successfully!"
echo "Auth dependencies: src/layers/auth-dependencies/auth-dependencies.zip"
echo "Common dependencies: src/layers/common-dependencies/common-dependencies.zip" 
