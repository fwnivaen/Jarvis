#!/bin/sh
set -eu
cd "$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
if [ "$(uname -s)" != Darwin ]; then exit 0; fi
if [ ! -x '.local/Jarvis Desktop.app/Contents/MacOS/JarvisDesktop' ] || [ native/JarvisDesktop.swift -nt '.local/Jarvis Desktop.app/Contents/MacOS/JarvisDesktop' ]; then
    sh native/build_desktop.sh
fi
if [ ! -x '.local/Jarvis Voice.app/Contents/MacOS/JarvisVoice' ] || [ native/JarvisVoice.swift -nt '.local/Jarvis Voice.app/Contents/MacOS/JarvisVoice' ]; then
    sh native/build_voice.sh
fi
/usr/bin/open '.local/Jarvis Desktop.app'
