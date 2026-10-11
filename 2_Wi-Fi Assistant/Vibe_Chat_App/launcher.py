"""Entry point for the Start Lab scripts.

Asks for an OpenAI API key on first launch, saves it to .env next to this
file, then opens the chat in the browser.
"""

from __future__ import annotations

import getpass
from pathlib import Path

from dotenv import dotenv_values, set_key

HERE = Path(__file__).resolve().parent
ENV_FILE = HERE / ".env"


def ensure_api_key() -> None:
    if dotenv_values(ENV_FILE).get("OPENAI_API_KEY"):
        return
    print()
    print("No OpenAI API key found.")
    print("Paste your key and press Enter (it will not show on screen).")
    print("Press Enter without a key to skip and use Ollama only.")
    key = getpass.getpass("OpenAI API key: ").strip()
    if not key:
        print("Skipped. You can add the key later in the .env file in this folder.")
        return
    ENV_FILE.touch(mode=0o600, exist_ok=True)
    set_key(str(ENV_FILE), "OPENAI_API_KEY", key, quote_mode="never")
    print(f"Saved to {ENV_FILE.name}.")


def main() -> None:
    ensure_api_key()
    print()
    print("Starting the chat. It opens in your browser.")
    print("Keep this window open. Close it to stop the chat.")
    print()
    import chat_box  # imported after .env exists, since it loads .env on import

    chat_box.main()


if __name__ == "__main__":
    main()
