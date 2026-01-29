#!/usr/bin/env bash
# Verify package does not contain playground or other unwanted files
set -e

echo "Building package..."
uv build --quiet

echo ""
echo "Checking wheel contents..."
if unzip -l dist/*.whl | grep -q "playground/"; then
    echo "❌ ERROR: playground/ found in wheel"
    exit 1
fi
echo "✓ Wheel does not contain playground/"

echo ""
echo "Checking sdist contents..."
if tar -tzf dist/*.tar.gz | grep -q "playground/"; then
    echo "❌ ERROR: playground/ found in sdist"
    exit 1
fi
echo "✓ Sdist does not contain playground/"

echo ""
echo "Package sizes:"
ls -lh dist/

echo ""
echo "✓ Package integrity check passed"
