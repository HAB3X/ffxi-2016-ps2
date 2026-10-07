#!/bin/bash
# Builds the four LandSandBoat server programs from Server/lsb (Linux, or an Intel Mac).
# They land in Server/lsb itself (xi_connect, xi_search, xi_world, xi_map), where the Server App looks for them.
set -e
cd "$(dirname "$0")/../lsb"
LSB="$(pwd)"
PY="$(command -v python3)"
# the build's code generator needs three Python modules; they go into a private folder, not the system Python
"$PY" -m venv "$LSB/.build-venv"
"$LSB/.build-venv/bin/pip" install --quiet jinja2 jsonschema ruamel.yaml
export VIRTUAL_ENV="$LSB/.build-venv" PATH="$LSB/.build-venv/bin:$PATH"
python tools/build.py
for p in xi_connect xi_search xi_world xi_map; do
  [ -x "$LSB/$p" ] || { echo "Build finished but $p is missing."; exit 1; }
done
echo "Built: xi_connect xi_search xi_world xi_map"
