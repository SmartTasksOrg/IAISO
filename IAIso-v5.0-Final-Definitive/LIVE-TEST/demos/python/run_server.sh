#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/../.."
python3 -m iaiso_live.server.app
