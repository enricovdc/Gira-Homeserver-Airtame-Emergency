#!/usr/bin/env bash
# Regenerate the deployable .hsl artefacts for both HSL2 and HSL3.
#
# Inputs:
#   GIRA_SDK_DIR  Path to the unpacked "Gira HomeServer SDK Doku" folder.
#                 Default: $HOME/Documents/Gira_HomeServer_SDK_Doku.
#   PYTHON27      Path to a Python 2.7 interpreter (HSL2 only).
#                 Default: python2.7
#   PYTHON39      Path to a Python 3.9 interpreter (HSL3 only).
#                 Default: python3.9
#
# Outputs:
#   projects/airtame_emergency/release/24815_AirtameEmergencyAlert.hsl
#   projects/airtame_emergency/debug/24815_AirtameEmergencyAlert.py
#   projects/airtame_emergency_hsl3/24815_airtame_emergency.hsl
#
# Both generators are idempotent given the same source files; the committed
# .hsl files in this repo were produced by running this script.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SDK="${GIRA_SDK_DIR:-$HOME/Documents/Gira_HomeServer_SDK_Doku}"
PYTHON27="${PYTHON27:-python2.7}"
PYTHON39="${PYTHON39:-python3.9}"

if [[ ! -d "$SDK/HSL/HSL2 SDK 2.0.7/framework" ]]; then
    echo "ERROR: GIRA_SDK_DIR='$SDK' missing 'HSL/HSL2 SDK 2.0.7/framework/'." >&2
    echo "Set GIRA_SDK_DIR to point at the unzipped 'Gira HomeServer SDK Doku'." >&2
    exit 1
fi

# -------- HSL2 ------------------------------------------------------------
# The HSL2 generator must run from the framework directory and looks up
# projects/<name>/{config.xml,src/}. Stage the project into a temp framework
# copy so we don't have to symlink into the SDK install.
HSL2_RUN="$(mktemp -d)"
trap 'rm -rf "$HSL2_RUN"' EXIT
cp -r "$SDK/HSL/HSL2 SDK 2.0.7/framework"/. "$HSL2_RUN/"
rm -rf "$HSL2_RUN/projects"
mkdir -p "$HSL2_RUN/projects/airtame_emergency/src" \
         "$HSL2_RUN/projects/airtame_emergency/release" \
         "$HSL2_RUN/projects/airtame_emergency/debug"
cp "$ROOT/projects/airtame_emergency/config.xml" \
   "$HSL2_RUN/projects/airtame_emergency/"
cp "$ROOT/projects/airtame_emergency/src/24815_AirtameEmergencyAlert.py" \
   "$HSL2_RUN/projects/airtame_emergency/src/"

echo "==> HSL2 generator..."
( cd "$HSL2_RUN" && "$PYTHON27" generator.pyc "airtame_emergency" UTF-8 )

mkdir -p "$ROOT/projects/airtame_emergency/release" \
         "$ROOT/projects/airtame_emergency/debug"
cp "$HSL2_RUN/projects/airtame_emergency/release/24815_AirtameEmergencyAlert.hsl" \
   "$ROOT/projects/airtame_emergency/release/"
cp "$HSL2_RUN/projects/airtame_emergency/debug/24815_AirtameEmergencyAlert.py" \
   "$ROOT/projects/airtame_emergency/debug/"
# Adopt any cosmetic normalisations the generator made to src/ so future
# regenerations are byte-stable.
cp "$HSL2_RUN/projects/airtame_emergency/src/24815_AirtameEmergencyAlert.py" \
   "$ROOT/projects/airtame_emergency/src/24815_AirtameEmergencyAlert.py"
echo "   -> projects/airtame_emergency/release/24815_AirtameEmergencyAlert.hsl"

# -------- HSL3 ------------------------------------------------------------
echo "==> HSL3 generator..."
( cd "$ROOT/projects/airtame_emergency_hsl3" \
  && "$PYTHON39" "$SDK/HSL/HSL3 SDK 3.0/generator/generator3.cpython-39.pyc" \
       --source config_airtame_emergency.json \
       --target  24815_airtame_emergency.hsl )
echo "   -> projects/airtame_emergency_hsl3/24815_airtame_emergency.hsl"

echo "Done."
