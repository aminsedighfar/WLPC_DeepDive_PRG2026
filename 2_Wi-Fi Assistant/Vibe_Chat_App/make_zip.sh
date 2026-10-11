#!/bin/bash
# For instructors: build the zip to hand out to participants.
# It contains only the files committed to git, so no .venv, .env, Uploads/ or Codes/.
set -euo pipefail
cd "$(dirname "$0")"

if [ -n "$(git status --porcelain -- .)" ]; then
    echo "This folder has uncommitted changes. Commit them first; the zip is built from git."
    git status --short -- .
    exit 1
fi

out="../Vibe_Chat_App.zip"
rm -f "$out"
# Run from this folder, git archive includes only this folder.
git archive --format=zip --prefix=Vibe_Chat_App/ -o "$out" HEAD
echo "Built $(cd .. && pwd)/Vibe_Chat_App.zip:"
unzip -l "$out"
