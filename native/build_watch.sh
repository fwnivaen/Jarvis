#!/bin/sh
set -eu
cd "$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
mkdir -p .local
swiftc native/WatchCard.swift -o .local/JarvisWatchCard -framework AppKit
