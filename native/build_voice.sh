#!/bin/sh
set -eu
cd "$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
APP=".local/Jarvis Voice.app"
mkdir -p "$APP/Contents/MacOS"
cat > "$APP/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>CFBundleExecutable</key><string>JarvisVoice</string>
<key>CFBundleIdentifier</key><string>local.jarvis.voice</string>
<key>CFBundleName</key><string>Jarvis Voice</string>
<key>CFBundleVersion</key><string>1</string>
<key>CFBundlePackageType</key><string>APPL</string>
<key>LSUIElement</key><true/>
<key>NSMicrophoneUsageDescription</key><string>Jarvis uses your microphone only while Mic is enabled.</string>
<key>NSSpeechRecognitionUsageDescription</key><string>Jarvis transcribes speech on this Mac to answer your questions.</string>
</dict></plist>
PLIST
swiftc native/JarvisVoice.swift -o "$APP/Contents/MacOS/JarvisVoice" -framework AppKit -framework AVFoundation -framework Speech
codesign --force --sign - "$APP" >/dev/null 2>&1
