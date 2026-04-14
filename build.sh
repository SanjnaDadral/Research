#!/usr/bin/env bash
# Exit on error
set -o errexit

echo "========================================="
echo "PaperAIzer Build Script for Render"
echo "========================================="
echo ""

echo "=== Step 1: Installing Python dependencies ==="
if pip install -r requirements.txt; then
    echo "✓ Dependencies installed successfully"
else
    echo "✗ Failed to install dependencies"
    exit 1
fi

echo ""
echo "=== Step 2: Collecting static files ==="
if python manage.py collectstatic --no-input --clear 2>&1; then
    echo "✓ Static files collected"
else
    echo "⚠ Static file collection had issues (continuing...)"
fi

echo ""
echo "========================================="
echo "✓ Build script completed!"
echo "========================================="
echo ""
echo "NOTE: Database migrations will run in Procfile release phase"
