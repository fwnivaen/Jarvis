#!/bin/sh
set -eu
cd "$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
mkdir -p .local
swiftc native/FocusCard.swift -o .local/JarvisFocusCard -framework AppKit
