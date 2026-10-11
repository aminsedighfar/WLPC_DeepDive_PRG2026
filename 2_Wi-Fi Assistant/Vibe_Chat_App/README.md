# Vibe Chat: getting started

You need an internet connection and your OpenAI API key.
The first launch takes about a minute. After that it starts in a few seconds.

---

## Mac

1. Unzip the **Vibe_Chat_App** folder and put it somewhere easy to find, such as your Desktop.
2. Open the folder and double-click **Start Lab.command**.
3. If macOS says it cannot open the file:
   - Click **Done** (not Move to Trash).
   - Open **System Settings → Privacy & Security**.
   - Scroll down and click **Open Anyway** next to "Start Lab.command", then confirm.
   - You only do this once.
4. A Terminal window opens. When it asks for your **OpenAI API key**, paste it and press **Enter**.
   The key does not show on screen while you paste. That is normal.
5. Wait. The chat opens in your web browser.
6. Keep the Terminal window open while you use the chat.

**To stop:** close the Terminal window.
**To start again:** double-click **Start Lab.command**. It will not ask for the key again.

---

## Windows

1. Right-click the zip file, choose **Extract All**, and extract the **Vibe_Chat_App** folder somewhere easy to find, such as your Desktop.
   Do not run it from inside the zip.
2. Open the folder and double-click **Start Lab** (the file named *Start Lab.bat*).
3. If you see **"Windows protected your PC"**:
   - Click **More info**.
   - Click **Run anyway**.
4. A black command window opens. When it asks for your **OpenAI API key**, paste it with **right-click** (or Ctrl+V) and press **Enter**.
   The key does not show on screen while you paste. That is normal.
5. Wait. The chat opens in your web browser.
6. Keep the black window open while you use the chat.

**To stop:** close the black window.
**To start again:** double-click **Start Lab**. It will not ask for the key again.

---

## Using the chat

- Pick the **LLM** at the top: **OpenAI** (uses your key) or **Ollama** (runs on your laptop, see below).
- Type in the chat box and press Enter.
- The **Agents and skills** panel on the right shows what you build.

## Optional: Ollama (local models)

1. Install Ollama from <https://ollama.com/download> and open it.
2. In a terminal, run: `ollama pull qwen2.5:7b`
3. In the chat, set **LLM** to **Ollama**.

## If something goes wrong

- **The browser did not open:** look in the Terminal or black window for a line like `http://127.0.0.1:7860` and open that address in your browser.
- **Wrong or expired API key:** close the app, delete the file named `.env` in the Vibe_Chat_App folder, and start again. It will ask for the key.
  On Mac the file is hidden: in Finder, press **Cmd + Shift + .** to show it.
- **"Could not install uv":** check your internet connection and start again.
- Still stuck? Raise your hand.
