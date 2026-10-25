#!/bin/sh
set -eu
cd "$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
APP=".local/Jarvis Desktop.app"
mkdir -p "$APP/Contents/MacOS"
cat > "$APP/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>CFBundleExecutable</key><string>JarvisDesktop</string>
<key>CFBundleIdentifier</key><string>local.jarvis.desktop</string>
<key>CFBundleName</key><string>Jarvis Desktop</string>
<key>CFBundleVersion</key><string>1</string>
<key>CFBundlePackageType</key><string>APPL</string>
<key>LSUIElement</key><true/>
<key>NSAppleEventsUsageDescription</key><string>Jarvis controls Music only when you ask it to play or pause.</string>
</dict></plist>
PLIST
swiftc native/JarvisDesktop.swift -o "$APP/Contents/MacOS/JarvisDesktop" -framework AppKit -framework AVFoundation -framework ApplicationServices -framework Carbon
codesign --force --sign - "$APP" >/dev/null 2>&1
