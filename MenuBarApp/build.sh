#!/bin/bash
# Build script for Captain's Log Menu Bar app

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BUILD_DIR="$SCRIPT_DIR/build"
APP_NAME="CaptainsLogMenuBar"

echo "Building $APP_NAME..."

# Create build directory
mkdir -p "$BUILD_DIR"

# Compile Swift
swiftc \
    -o "$BUILD_DIR/$APP_NAME" \
    -target arm64-apple-macos12.0 \
    -framework SwiftUI \
    -framework AppKit \
    -parse-as-library \
    "$SCRIPT_DIR/CaptainsLogMenuBar.swift"

# Create app bundle structure
APP_BUNDLE="$BUILD_DIR/$APP_NAME.app"
mkdir -p "$APP_BUNDLE/Contents/MacOS"
mkdir -p "$APP_BUNDLE/Contents/Resources"

# Copy executable
cp "$BUILD_DIR/$APP_NAME" "$APP_BUNDLE/Contents/MacOS/"

# Copy Info.plist
cp "$SCRIPT_DIR/Info.plist" "$APP_BUNDLE/Contents/"

# Clear quarantine attribute
xattr -c "$APP_BUNDLE" 2>/dev/null || true

echo "Build complete: $APP_BUNDLE"
echo ""
echo "To install, run:"
echo "  cp -r \"$APP_BUNDLE\" /Applications/"
echo ""
echo "To launch:"
echo "  open /Applications/$APP_NAME.app"
