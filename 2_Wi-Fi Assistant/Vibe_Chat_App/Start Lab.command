#!/bin/bash
# Double-click to start the vibe chat on macOS.
cd "$(dirname "$0")" || exit 1
export PATH="$HOME/.local/bin:$PATH"

if ! command -v uv >/dev/null 2>&1; then
    echo "Installing uv (one time only)..."
    curl -LsSf https://astral.sh/uv/install.sh | sh || {
        echo "Could not install uv. Check your internet connection."
        read -r -p "Press Enter to close."
        exit 1
    }
fi

# A .venv copied from another computer (for example inside a zip) cannot run here.
if [ -d .venv ] && ! .venv/bin/python -c "" >/dev/null 2>&1; then
    echo "Rebuilding the Python environment for this computer..."
    rm -rf .venv
fi

echo "Preparing the lab. The first launch downloads Python and packages (about a minute)."
uv run --quiet launcher.py
read -r -p "Chat stopped. Press Enter to close."
