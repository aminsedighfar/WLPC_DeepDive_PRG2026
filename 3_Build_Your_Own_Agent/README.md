# Wi-Fi Agent Builder - prompt pack

Use this pack to build a Wi-Fi engineering agent with your own AI coding tool: Claude Code, Claude Cowork,
OpenAI Codex, Cursor, GitHub Copilot (VS Code or CLI), or similar. The result has:

- an **orchestrator** that routes every request to exactly one specialist subagent
- **specialists** or **sub-agents**, each with one narrow job, their own tools and their own model
- a **Programmer** specialist, the only one allowed to write code
- a **local web UI** with:
  - chat, history, file upload and per-chat model choice
  - a report viewer
  - settings for agent name and avatar, LLM provider (including Ollama), agent instructions and models, and API tokens

## How to use this pack

1. Create an empty folder and open it in your tool, in its agent / coding mode.
2. Paste **Prompt 1**. It builds everything without asking questions:
   - the framework, the orchestrator, the **Wi-Fi Assistant** and the **Programmer**
   - the full web UI with settings

   It then starts the UI and gives you the link. Open it and chat.
3. When you're ready, paste **Prompt 2** into the same tool session (not into the web chat). It adds the
   **Checklist Assessor**, **Capture Analyst** and **Survey File Reader**. Upload sample files in the web chat
   first, so they are tested on real data.
4. Optional add-ons, pasted later:
   - **Add-on A:** one live system (Mist, Meraki…)
   - **Add-on B:** any new specialist
5. Edit anything in brackets `[like this]` before pasting.

---

## Prompt 1: Agent, core specialists and web UI

````markdown
You are going to build a Wi-Fi engineering agent in this folder, using YOUR OWN native agent features, plus a
local web UI to chat with it. Build everything in one go without asking me questions. Test as you go, and at the
end start the UI and give me its link.

First, detect which tool you are (Claude Code, Claude Cowork, OpenAI Codex, Cursor, GitHub Copilot, or other)
and tell me in one line. Do not write an agent application or use an agent SDK for the agent logic. You (the
main session) are the agent: you are the Orchestrator, and the specialists are your subagents. The web UI is a
thin shell around your own headless CLI and contains no agent logic.

Only stop to ask me if you are truly blocked (for example, your CLI is not installed or not signed in). Make
sensible choices otherwise, and list them at the end.

=== THE FRAMEWORK ===

1. Orchestrator (you, the main session)
- You route; you do not do the work. For every request, pick exactly ONE specialist and delegate to it.
- Read the whole conversation, not just the last message. A follow-up ("the list", "that SSID", "the pcap",
  "do it again") stays with the specialist that was handling that job.
- If nothing matches, answer briefly that you only help with this agent's specialists, and list them. Do not
  answer off-topic questions (geography, weather, trivia, news unrelated to Wi-Fi).
- After the specialist returns, relay its result faithfully, starting with **[<key>]** so the user sees who
  handled it. Never add measurements, file contents or results that the specialist did not produce.

2. Specialists (one subagent each)
- Each specialist has ONE narrow job, written as "Does" and "Does not" rules.
- Each gets the smallest set of tools that job needs, and nothing else.
- Each gets a model sized to the job, as a tier:
  - a fast tier (e.g. haiku) for specialists that only run scripts or read files
  - a balanced tier (e.g. sonnet) for Q&A
  - the strongest tier (e.g. opus) for the Programmer and anything that writes to a live system
- The description of each specialist states exactly when to use it, so routing is unambiguous.

3. Author / executor split (this is what makes the agent deterministic)
- The Programmer is the ONLY specialist allowed to write or change code. It saves scripts in Codes/ or in a
  skill's scripts/ folder, and test-runs them.
- Operational specialists never write code. They list the input files, run an existing script with arguments,
  and paste its output. If the script is missing, they say so and ask the Programmer.
- Package each repeatable job as a skill: a SKILL.md with a numbered workflow that runs one script in
  scripts/. The specialist uses the skill instead of re-implementing the logic in prose.

4. Live systems through MCP
- Controllers, monitoring platforms and cloud APIs are reached only through MCP servers. Use an existing
  server if there is one; otherwise the Programmer writes a small one (Python, mcp.server.fastmcp, synchronous
  tools, one tool per API operation, plus a raw_request tool).
- Each MCP server gets its own specialist, and only that specialist uses those tools.
- Secrets live in a gitignored .env file, which the server loads itself. Never put tokens in instructions,
  skills, config files, code or chat.

5. Guardrails (apply to every specialist)
- Input files in Files/ (and any original the user gives) are read-only. Every change goes to a NEW file in
  Outputs/ (name_modified.esx, then name_modified(1).esx, (2)…). Never overwrite.
- Stay inside this project folder.
- Never invent a filename: list the folder first and use only a name that exists. If several match, ask which.
- Never invent measurements, IDs or API results. Paste tool output.
- Stay vendor-neutral unless the user names a vendor.
- Before any create/update/delete on a live system:
  - show the exact change and wait for the user's "yes"
  - after the write, read the object back and report the fields that prove it worked

=== DECISIONS ALREADY MADE (do not interview me) ===

- **Purpose:** answer Wi-Fi questions; assess Wi-Fi Explorer scans and packet captures against a Wi-Fi checklist;
  analyse captures frame by frame; read and edit Ekahau / OpenIntent design files; let the Programmer build MCP
  servers for Wi-Fi platforms (Juniper Mist, Cisco Meraki…) so the agent can query and change them later.
- **Input files:** Wi-Fi Explorer CSV, pcap/pcapng, Ekahau .esx, OpenIntent, CSV. Users upload them in the web chat
  (or attach them in your tool). They land in Files/ as read-only copies, so users never manage that folder.
- **Live systems:** none connected now. The Programmer writes MCP servers on request; changes are allowed, but
  only with confirm-then-verify. Tokens are entered in Settings → API tokens. Put placeholders for Juniper Mist
  (MIST_API_TOKEN, MIST_BASE_URL, MIST_ORG_ID) and Cisco Meraki (MERAKI_API_KEY, MERAKI_BASE_URL, MERAKI_ORG_ID)
  in .env.example.
- **Design rules:** WLAN Pros Wi-Fi Checklist v4 values:
  - 2.4 GHz channels 1/6/11, 20 MHz only
  - RSSI -67 dBm (2.4 GHz) / -65 dBm (5/6 GHz)
  - co-/adjacent-channel interference threshold -85 dBm
  - MBR ≥ 12 Mbps, no 802.11b rates
  - WPA3 recommended, and required in 6 GHz (with PMF); no WPA2/3 transition, no TKIP/WEP
  - channel utilisation < 40 % (2.4 GHz) / < 20 % (5/6 GHz)
  - < 40 clients per radio, ≤ 4 SSIDs
  - 6 GHz on PSC with RNR discovery
- **Never-do rules:** only the guardrails above.
- **Reports:** Markdown files in Outputs/, viewed in the web UI's report viewer.
- **Identity:** the agent is called "Wi-Fi Agent", with the 🛜 avatar. Both can be changed in Settings.
- **LLM providers:** the user's subscription login, an API key, and local models via Ollama, all switchable in
  Settings.
- **Roster for this prompt:** Orchestrator + `wifi` + `programmer`. A second prompt will add `checklist`,
  `capture` and `survey`, so make the routing table, the UI and the settings pick up new specialists
  automatically.

=== PLATFORM MAPPING (starting hints; check your own current docs) ===

| Concept | Claude Code | Claude Cowork | Codex | Cursor | GitHub Copilot |
|---|---|---|---|---|---|
| Orchestrator rules | CLAUDE.md | project instructions / CLAUDE.md | AGENTS.md | AGENTS.md or .cursor/rules/*.mdc (always apply) | AGENTS.md or .github/copilot-instructions.md |
| Specialists | .claude/agents/<key>.md (name, description, tools, model) | plugin agents/*.md | .codex/agents/<key>.toml (name, description, developer_instructions, model, sandbox_mode) | .cursor/agents/<key>.md | .github/agents/<key>.agent.md (custom agents) |
| Skills | .claude/skills/<name>/SKILL.md + scripts/ | plugin skills/ | .agents/skills/ | .cursor/skills/ | .github/skills/ |
| MCP servers | .mcp.json | connectors / plugin .mcp.json | [mcp_servers.*] in .codex/config.toml | .cursor/mcp.json | .vscode/mcp.json |
| Guardrails | permissions.deny in .claude/settings.json | folder permissions | sandbox_mode + approval policy | permissions / .cursorignore | tool approvals / content exclusions |
| Prompt hook (file intake) | UserPromptSubmit hook | — | — | hooks (beforeSubmitPrompt) | agent hooks, if available |
| Headless CLI (for the UI) | claude -p --output-format stream-json | none: use the Claude Code CLI if installed | codex exec --json (+ resume) | cursor-agent -p --output-format stream-json | copilot -p |

Rules for this table:
- Check your current documentation for every row. If something differs, use the current equivalent and tell me
  what you changed and why.
- If your tool has no real subagents, emulate them: create one role file per specialist. The orchestrator rules
  say: "for each request, load the ONE matching role file and follow only it until the job is done". The tool
  allowlists then become written rules.
- Never claim a feature works until you have tested it.

=== PART A: FOUNDATION ===

- **Orchestrator rules file** (see mapping):
  - the framework rules above
  - a routing table (key → specialist → when to use), with tie-breakers between specialists whose jobs are
    close
  - an identity block between `<!-- identity:start -->` and `<!-- identity:end -->`, containing "Your name is
    Wi-Fi Agent. Introduce yourself with this name when asked."
  - an "Attachments" section: files arrive in Files/; always pass Files/... paths to specialists
- **Folders:** Files/ (inputs, read-only), Outputs/ (reports and modified copies), Codes/ (scripts, hooks, MCP
  servers, the UI), plus your native config folders.
- **Python with uv:** a pyproject.toml, scripts run with `uv run python ...`, minimal dependencies.
- **Project files:**
  - `.gitignore`: .env, .venv, caches, Files/, Outputs/, .chat/
  - `.env.example`: variable names only, grouped under `# <System>` comment headers
  - an empty MCP config
- **Guardrails:**
  - deny editing or writing Files/**, and deny reading .env
  - deny rm / chmod / mv on Files/ where your tool supports deny rules
- **File intake:** if your tool has a prompt hook, add a small standard-library script
  (Codes/hooks/intake_attachments.py) that:
  - finds attached paths in the prompt (`@"path"`, `@path`, quoted absolute paths)
  - copies files from outside the project into Files/ and makes the copy read-only
  - reuses an identical file (same SHA-256); saves a different file with the same name as name(1).ext
  - tells the orchestrator the Files/... path
- **Script convention:** write outputs to Outputs/, never overwrite (X.md → X(1).md), print the result, and end
  with `Saved: Outputs/...`.
- **Sandbox:** if it blocks the uv cache or network, fix it inside the project (e.g. UV_CACHE_DIR=.uv-cache,
  gitignored) instead of loosening security.

=== PART B: CORE SPECIALISTS ===

B1. `wifi` — Wi-Fi Assistant
- Model tier: balanced (e.g. sonnet).
- Tools: read, glob/list, grep, web search, web fetch. No skill.
- Description (for routing): Use for Wi-Fi / WLAN / RF / 802.11 standards, design and troubleshooting questions,
  for listing which input files are available in Files/, and for researching Wi-Fi topics on the web. Does not
  write code, run scripts, analyse files in depth or call live systems.
- Does:
  - answers questions on 802.11 a/b/g/n/ac/ax/be, security (WPA2/WPA3/OWE/802.1X, PMF), roaming (802.11k/r/v),
    channel planning, 6 GHz (PSC, RNR, AFC, LPI/SP), MLO, PoE and troubleshooting
  - lists Files/ and Outputs/ with exact names
  - explains using the design rules above
  - searches the web for current or vendor-specific facts, and lists the sources
- Does not:
  - write code or config (→ programmer)
  - score files, dissect captures, read survey files, or call live systems (other specialists, now or later)
  - modify Files/, invent measurements, favour a vendor unless the user names one, or answer non-Wi-Fi questions
- Steps:
  1. If the question is about files, list Files/.
  2. Otherwise answer concisely, and say when something depends on the vendor or the regulatory domain.
  3. List the sources if the web was used.

B2. `programmer` — Programmer (the ONLY specialist that writes code)
- Model tier: strongest (e.g. opus).
- Tools: read, write, edit, glob, grep, shell, web search, web fetch.
- Description (for routing): Use when the user wants a new or changed script, skill script, MCP server for a
  Wi-Fi platform API (Juniper Mist, Cisco Meraki, Aruba Central, Extreme, NetBeez…), or a new specialist/skill
  wired in. Does not call live systems or edit files in Files/.
- Does:
  - writes and test-runs Python scripts in Codes/ or a skill's scripts/ folder, plus the SKILL.md around each
  - writes MCP servers in Codes/mcp/<system>_server.py and registers them in the MCP config; then creates the
    matching specialist and adds its row to the routing table and README
  - adds dependencies with `uv add` (minimal) and runs everything with `uv run python ...`
  - test-runs on a real file from Files/, or a synthetic one under Outputs/test/, and pastes the real output
- Does not:
  - call live systems or use another specialist's MCP tools
  - modify Files/
  - put secrets anywhere except .env (only variable NAMES go in .env.example, under `# <System>`)
- Script conventions:
  - argparse CLI, input path as an argument, no hard-coded filenames
  - inputs read-only; outputs to Outputs/ with next-free naming
  - print Markdown and end with `Saved: Outputs/...`
  - missing data is reported as UNKNOWN; errors start with `ERROR:`
- MCP conventions:
  - FastMCP, synchronous tools, httpx, python-dotenv loading .env from the project root
  - one tool per API operation: list_/get_ for reads; create_/update_/delete_ for writes, with a docstring
    saying "WRITE: requires user confirmation"
  - plus raw_request(method, path, body=None)
  - base URL and token come from env vars
- Steps:
  1. Restate the spec.
  2. Read neighbouring code, then write the code.
  3. Test-run it and paste the actual output.
  4. Report the files changed, how to run them, and what is untested.

=== PART C: WEB UI AND SETTINGS ===

Architecture
- Python standard library only (http.server, threading, subprocess, urllib). Bind to 127.0.0.1.
- Every POST needs an X-Settings-Token header. The token is random per server start and embedded in the page.
- Files:
  - Codes/chat_ui/server.py, index.html, viewer.html
  - Codes/settings_ui/server.py + index.html: a shared module whose `api(method, path, body)` the chat server
    reuses; the settings page also runs standalone
- Local state in .chat/ (gitignored): threads/, llm.json, identity.json, avatar.*, history/, tmp/.
- Front-end libraries: only marked and DOMPurify, from cdnjs with exact pinned versions. Everything else is
  inline.
- Design:
  - CSS color tokens with light/dark mode; responsive at phone width
  - add a launch/preview config if your tool has one; otherwise print the start command
- Specialists are discovered by reading the specialist folder at runtime. Nothing in the UI hard-codes the
  roster.

Runner adapter (the only tool-specific part)
- Implement `run(prompt, session_id, resume: bool, model, env) -> stream of events`, using your headless CLI.
  For Claude Code:
  `claude -p <prompt> --output-format stream-json --verbose --permission-mode acceptEdits --allowedTools <list>
  (--session-id <uuid> | --resume <uuid>) [--model <m>]`.
- Before writing the parser, check your CLI's `--help` and capture ONE real event stream.
- Map the stream to UI events:
  - status
  - route: a subagent call, with the subagent key
  - step: a tool call; attribute it to the specialist through the parent tool-use id
  - text: orchestrator text only
  - done: final text, is_error, cost, duration
- Each chat thread owns one session id: the first message starts it and later messages resume it.
- Allowed tools in headless mode:
  - subagent calls, read/glob/grep, web, write/edit
  - `uv run python *`, `uv add *`
  - every server in the MCP config
  The deny rules still apply.
- If your tool has no headless CLI (e.g. Cowork), use the Claude Code CLI if it is installed. Otherwise tell me.

Chat (/)
- **Sidebar:**
  - the agent's avatar and name
  - "+ New chat"
  - threads, newest first: title from the first message, relative time, specialists used, a dot while running
  - click a thread to continue it
  - a Settings link
- **Top bar:**
  - thread title
  - provider badge (links to Settings)
  - model picker per thread. It is provider-aware: Claude tiers, or the local Ollama models with "not ready"
    marked. "Default" uses the settings value.
- **Composer:**
  - textarea: Enter sends, Shift+Enter adds a new line
  - attach button plus drag-and-drop; multiple files with progress, up to 2 GB
  - uploads stream to Files/ as read-only copies: identical file (SHA-256) reused, a different file with the same
    name saved as name(1)
  - the prompt tells the orchestrator the Files/... paths
  - Stop button while running
- **Live answer (Server-Sent Events, replayable on reconnect):**
  - status line with spinner
  - a "→ Specialist (key)" badge per route
  - collapsible "N steps" list (who, tool, detail such as the exact command)
  - streamed orchestrator text
- **Final answer:**
  - Markdown rendered and sanitised
  - links to Outputs/*.md open the report viewer; other Outputs files download
  - meta line: provider, model, duration, cost
- **Empty state:**
  - "Hi, I'm <name>"
  - one roster card per specialist found (name, key, model)
  - suggestion chips for the specialists that exist
- **Errors:** error bubble.
- **Auth:**
  - If the provider is the subscription login, check auth status before each run (e.g.
    `claude auth status --json`). If the user is signed out, or the reply is an auth error, show a "Sign in" card.
  - The card opens a dialog. The server starts the login command (e.g. `claude auth login`), captures the
    sign-in URL and shows it, takes the code the user pastes (sent to the process's stdin), confirms success, then
    offers "Retry last message".
  - An API-key rejection shows a card linking to Settings.

Report viewer (/view/Outputs/<file>)
- Reads only from Outputs/, with path-traversal checks. Markdown rendered with marked + DOMPurify.
- Sticky top bar: back to chat, path, Raw, Download, Print/PDF (print CSS hides the controls).
- Table of contents from h2/h3.
- Tables:
  - wrapped in horizontal scroll, sticky header
  - status cells (✅ PASS / ⚠️ WARN / ❌ FAIL / ❔ UNKNOWN / ➖ N/A / ℹ️ INFO) become coloured pills
  - evidence columns wrap; MAC addresses in monospace
- A "Results" table (Band | Pass | Warn | Fail | Assessed) becomes per-band score cards with a stacked bar. A band
  with nothing assessed says so.
- A table with an "Item" column and status cells gets filter buttons: All / Fail / Warn / Unknown / Pass.

Settings (/settings) — tabs: General · LLM provider · Agents · API tokens
1. **General: identity.**
   - Agent name, 1–40 characters.
   - Avatar:
     - choose from ~24 emoji (🛜 📡 📶 🤖 🦉 🐙 🚀 🧠 …)
     - or upload an image (PNG/JPG/SVG/WebP, ≤ 1 MB, saved as .chat/avatar.<ext>; sanitise SVG or refuse
       scripts)
     - or reset to the default
     - live preview of the sidebar header and a chat bubble
   - Stored in .chat/identity.json.
   - Used in:
     - the sidebar header, page title and favicon (emoji rendered in an SVG favicon, or the image)
     - the assistant message avatar and the empty state
   - Saving also rewrites the identity block in the orchestrator rules file (after backing it up), so the agent
     introduces itself with the new name.
2. **LLM provider.** Cards: subscription login | API key | Ollama (local). Show only the providers your runner
   supports.
   - **Subscription:** show signed-in status.
   - **API key:** write-only field saved to .env (e.g. ANTHROPIC_API_KEY). The UI shows only "set (N chars)".
     Clear asks for confirmation.
   - **Ollama:**
     - URL, localhost only
     - status (version, or "not reachable")
     - models table from /api/tags, plus /api/show for num_ctx: name, params, size, max context, context in use,
       capabilities, and a ready flag (tools + ≥ 32K context, or a cloud model)
     - "Make 64K copy": POST /api/create {model: "<name>-64k", from: "<name>", parameters: {num_ctx: 65536}}
     - default chat model
     - tier mapping (fast/balanced/strongest → local model), showing which specialists use each tier
     - a note that :cloud models are not local and web search is unavailable
   - Wire the provider into the runner. For Claude Code:
     - API key: inject ANTHROPIC_API_KEY.
     - Ollama: set ANTHROPIC_BASE_URL=<url>, ANTHROPIC_AUTH_TOKEN=ollama, ANTHROPIC_API_KEY="",
       ANTHROPIC_DEFAULT_{HAIKU,SONNET,OPUS}_MODEL=<mapped>, CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1.
     - Subscription: strip all ANTHROPIC_* variables.
     For other tools, use their own provider configuration.
3. **Agents.** A list on the left (Orchestrator, then every specialist found) and an editor on the right.
   - **Orchestrator:** default model (for the subscription or API key provider) and the full rules file in a
     monospace editor.
   - **Specialist:**
     - model tier dropdown
     - routing description (when to use)
     - instructions body (Does / Does not / Steps)
     - tools shown read-only ("ask the Programmer to change tools")
   - Editing:
     - unsaved-change dot; Save / Discard; a browser warning before leaving with unsaved edits
     - validation: no empty instructions, a description of at least one sentence, and the orchestrator rules
       can't be emptied
   - Version history: every save first copies the old file to .chat/history/<key>-<timestamp>.md. "Previous
     versions" loads a copy into the editor, and Save restores it.
   - Frontmatter values containing ": " are written quoted.
4. **API tokens.**
   - One card per `# <System>` group in .env.example, plus "Other" for extra variables in .env (excluding the LLM
     provider's variables).
   - Secrets are write-only and show "set (N chars)". Values of names ending in _URL/_ID/_HOST/_REGION are
     shown.
   - "Add a variable" (UPPER_SNAKE_CASE); Clear asks for confirmation.
   - .env is written with permissions 600 and is never sent to the browser.

=== PART D: TEST, README, LAUNCH ===

Tests (show me the results):
- Routing:
  - "What's the difference between 802.11k, 802.11r and 802.11v?" → wifi
  - "Write a script that counts SSIDs in a CSV" → programmer
  - "What's the capital of Peru?" → declined, with the list of specialists
- Upload: a duplicate is reused; a different file with the same name gets (1).
- A thread survives a server restart and resumes the same session.
- One message per available provider. If a provider can't be used here (no key, Ollama not running), say so.
- The auth card appears when signed out.
- Report viewer: on a small sample report in Outputs/test/, including status pills and filters.
- Agents tab: save → restore previous version leaves the file byte-identical.
- Identity: changing the name and avatar shows everywhere, and the orchestrator answers with its new name. Then
  restore the defaults.
- Test in your own browser tab. Never type into my open pages or change my settings; restore anything you
  touch.

README.md:
- the roster table
- how to start the UI
- every settings tab, and where state and secrets live
- how to add a specialist (Programmer writes the script → skill → specialist file → routing row → test)
- example prompts for each specialist
- how to see which specialist handled a request (the [key] prefix and the route badge)
- known limits

Launch: start the UI and give me the link. End with:
- a short list of the choices you made and anything that differs from the platform table
- a reminder that I can paste Prompt 2 to add the Checklist Assessor, Capture Analyst and Survey File Reader

=== KNOWN PITFALLS (from a previous build; plan for them) ===

- Subagents and hooks are loaded at session start. The web UI starts a fresh CLI run per message, so it picks up
  changes immediately; your own build session may need a restart.
- Test every script on a real sample. Synthetic tests prove the code runs, not that it parses real files.
- Local models via Ollama load with a 4K context by default. That truncates the agent's instructions and gives
  off-topic answers. Models need tool support and at least 32K context, and answers take minutes.
- A headless CLI's login can expire silently. Check auth status before running, and offer the sign-in flow.
- When testing the UI, never type into or change the user's own open pages or settings.

Start now.
````

---

## Prompt 2: Add the analysis specialists

Paste this into the same tool session you used for Prompt 1. To get real-data tests, first upload one sample of
each file type in the web chat: a Wi-Fi Explorer CSV, a pcap/pcapng and an Ekahau .esx.

````markdown
Add three specialists to the Wi-Fi agent you built: `checklist`, `capture` and `survey`. Keep every framework
rule and guardrail from the first prompt.

For EACH specialist, in this order:
1. Restate its spec in 5–8 bullets.
2. Have the Programmer write and test-run the script on a real sample from Files/:
   - list Files/ and use a matching file if there is one
   - otherwise use a synthetic file kept in Outputs/test/, and tell me to upload a real one
   Show me the spec you gave the Programmer and the real output.
3. Write the skill: SKILL.md with a numbered workflow that runs one script.
4. Write the specialist file: description, tool allowlist, model tier, Does / Does not / Steps.
5. Add its row to the routing table, with tie-breakers against the specialists that already exist.
6. Check that it appears in the web UI: Agents tab, empty-state roster, and suggestion chips. Its report must
   open in the report viewer.
7. Give me 2–3 routing test prompts, including one that must NOT route to it.

When all three are done, run every routing test through the web UI and show me which specialist answered each.

=== SPECIALIST 1: `checklist` — Checklist Assessor (skill `wifi-checklist-assess`) ===

- Model tier: fast (e.g. haiku). Tools: read, glob, shell (to run the script). No write/edit.
- Description (for routing): Use when the user wants a Wi-Fi Explorer scan (.csv) or a capture (.pcap/.pcapng)
  assessed, validated or scored against the Wi-Fi checklist / best practices (channels, widths, RSSI, CCC/ACI,
  security, MBR, 802.11k/r/v, BSS load, SSID count, 6 GHz PSC/RNR, MLO). Produces a Markdown report. Does not
  write code or do frame-level troubleshooting.
- Rules file: wlanpros_rules.json next to SKILL.md. The user edits this file, never the prose. Values (WLAN Pros
  Wi-Fi Checklist v4) [replace with your own if you use a different checklist]:
  - 2.4 GHz channels 1/6/11 only
  - widths:
    - 2.4 GHz: 20 MHz pass, 40 fail
    - 5 GHz: 20/40 pass, 80/160 fail
    - 6 GHz: 20/40 pass, 80/160 warn ("check CCC"), 320 fail
  - co-/adjacent-channel neighbours count as interference above -85 dBm
  - primary and secondary RSSI: -67 dBm (2.4 GHz) / -65 dBm (5/6 GHz)
  - Tx power targets: 7 / 13 / 16 dBm, ±3 dB
  - MBR ≥ 12 Mbps; no 802.11b rates in 2.4 GHz
  - channel utilisation < 40 % (2.4 GHz) / < 20 % (5/6 GHz); < 40 clients per radio; ≤ 4 SSIDs per radio
  - beacon interval 100 TU; DTIM 1
  - WPA3: recommended in 2.4/5 GHz, required in 6 GHz. PMF: recommended in 2.4/5 GHz, required in 6 GHz. No
    WPA2/WPA3 transition, no TKIP/WEP/WPA1.
  - bonded 5 GHz channels keep the primary on the high side; in 6 GHz the primary is consistent and on a PSC
- Script `assess_checklist.py <file> [--ssid <target>] [--rules <path>]`:
  - CSV loader (Wi-Fi Explorer export):
    - find the header row; map columns by name aliases (SSID/Network Name, BSSID, Channel, Band, Channel
      Width, Signal/RSSI, Security, Basic/Supported Rates, Station Count, Channel Utilization, Country, Beacon
      Interval, DTIM, 802.11k/r/v, PMF, Tx Power…)
    - list in the report which columns were used and which were ignored
  - pcap/pcapng loader (scapy, streaming):
    - read beacons and probe responses per BSSID; RSSI = mean radiotap dBm; band and channel from frequency
    - parse information elements: SSID/hidden, rates (basic bit), DS channel, TIM/DTIM, country, BSS Load,
      TPC/power constraint, ERP, RSN (ciphers, AKMs, MFPR/MFPC), HT/VHT/HE-6 GHz/EHT operation (width),
      RM capabilities (k), mobility domain/FT AKMs (r), extended capabilities (v), WMM,
      HS2.0/Interworking/RCOI, RNR, Multi-Link (MLD)
  - scope: with --ssid, assess that SSID's BSSs and use every other BSS as a neighbour for CCC/ACI; without it,
    assess all visible SSIDs and say so
  - status per item and band: ✅ PASS, ⚠️ WARN, ❌ FAIL, ❔ UNKNOWN (not in the source), ➖ N/A, ℹ️ INFO
  - report sections:
    - header: file, date, rules, scope, source notes
    - "Results" table: Band | ✅ Pass | ⚠️ Warn | ❌ Fail | Assessed items
    - "Checklist" table: # | Item | 2.4 GHz | 5 GHz | 6 GHz | Evidence
    - a "Not assessable from a scan/capture" list (configuration-only items)
    - "BSS assessed" appendix table
  - saved as Outputs/<file>[_<ssid>]_checklist.md
- Skill workflow:
  1. List Files/ (.csv, .pcap, .pcapng); ask if several match.
  2. Get the target SSID if the user named one.
  3. Run the script.
  4. On `ERROR:`, paste it and refer the user to the Programmer.
  5. Return the report verbatim with the saved path.
- Does not: write code, change thresholds itself, invent values, or do frame-level analysis (→ capture).
- Routing tests:
  - "Check the scan I uploaded against the Wi-Fi checklist for SSID [CORP]"
  - "Validate this capture against best practices"

=== SPECIALIST 2: `capture` — Capture Analyst (skill `pcap-frame-analysis`) ===

- Model tier: fast (e.g. haiku). Tools: read, glob, shell. No write/edit.
- Description (for routing): Use when the user wants a .pcap/.pcapng analysed at frame level: frame type mix,
  retry rate, deauth/disassoc reason codes, auth/assoc/reassoc (roaming) events and status codes, EAPOL 4-way
  handshakes, top transmitters, channels and signal. Produces a Markdown report. Does not score against the
  checklist or write code.
- Script `capture_summary.py <file> [--mac <client-or-bssid>] [--max-events 150]` (scapy, streaming). Report
  sections:
  - **Summary:** frames, 802.11 vs non-802.11, time span. If there is no 802.11 frame, say the capture was not
    taken in monitor mode.
  - **Frame mix:** per type with retry %, then the top subtypes.
  - **Channels:** from radiotap frequency.
  - **Top transmitters:** frames, retry %, average/min/max RSSI, SSID if it is an AP.
  - **Deauth/disassoc reason codes:** with meanings; "PMF-protected" when the reason is encrypted.
  - **Auth/assoc status codes:** with meanings.
  - **EAPOL 4-way handshakes:** per client/AP — M1→M4 sequence and whether it completed.
  - **Roaming:** reassociation requests, from → to.
  - **Probe requests:** count, clients, SSIDs probed.
  - **Event timeline:** limited to --max-events.

  Saved as Outputs/<file>[_<mac>]_capture.md.
- Skill workflow:
  1. List Files/*.pcap*; ask if ambiguous.
  2. Use --mac only with a MAC the user gave or one that appears in a previous output.
  3. Run the script.
  4. Return the report. When answering a specific question, quote the relevant rows and add no new numbers.
- Does not: write code, invent counts or conclusions, or score against the checklist (→ checklist).
- Routing tests:
  - "Why does my client keep disconnecting? Look at the capture I uploaded"
  - "Show me the EAPOL handshakes in that capture" (a follow-up, so it must stay with capture)

=== SPECIALIST 3: `survey` — Survey File Reader (skill `survey-file-inspect`) ===

- Model tier: fast (e.g. haiku). Tools: read, glob, shell. No write/edit.
- Description (for routing): Use when the user wants an Ekahau .esx or OpenIntent design/survey file read,
  summarised (project, floors, APs, radios, bands, channels, widths, Tx power, antennas) or edited. Edits are
  always written to a new file in Outputs/. Does not write code or assess scans.
- Script `survey_tool.py` with two sub-commands:
  - `inspect <file>`
    - Ekahau .esx (a zip of JSON files): project, floors (floorPlans.json), APs (accessPoints.json), and
      simulated radios (simulatedRadios.json) with channel(s), width (= 20 MHz × channels listed),
      transmitPower shown raw with no unit assumed, enabled flag and antenna height; plus the measured radio
      count and the archive members.
    - Any other zip/JSON, e.g. OpenIntent: a structural summary only (members, keys, list sizes, field names),
      with no guessed meaning.
    - Inspect the real sample first and adapt to its actual layout.
  - `edit <file.esx> [--rename-ap OLD=NEW] [--set-channel AP:IDX=CH[,CH]] [--set-power AP:IDX=VALUE]
    [--disable-radio AP:IDX] [--enable-radio AP:IDX]`
    - Writes Outputs/<name>_modified.esx (then (1), (2)…) and copies every other archive member
      byte-for-byte.
    - Errors if an AP name matches zero or several APs, and lists the existing names.
- Skill workflow for an edit:
  1. Run inspect first, so names and radio indexes come from the file.
  2. Show the exact change list and the output name, and wait for "yes".
  3. Run edit.
  4. Run inspect on the new file and report the rows that prove the change.
- Does not: write code, modify originals, or invent AP names, channels or power values.
- Routing tests:
  - "Summarise the APs and channels in the design file I uploaded"
  - "In that design, set AP-01 radio 1 to channel 149/153"

Finally:
- Update the README: roster table, example prompts, and known limits (e.g. which parsers were only tested on
  synthetic files).
- List anything you could not test on real data.
````

---

## Add-on A: Live-system specialist (optional; one per platform)

````markdown
Add a live-system specialist for [PLATFORM, e.g. Juniper Mist] to the Wi-Fi agent. Keep every framework rule.

Key: [mist]. Model tier: strongest (e.g. opus) if writes are allowed, otherwise balanced.
MCP server: [existing server: name and how to install] OR "Programmer writes Codes/mcp/[mist]_server.py".
Env vars (names only, in .env.example under `# [Juniper Mist]`; I will enter the values in Settings → API
tokens): [MIST_API_TOKEN, MIST_BASE_URL, MIST_ORG_ID].
Access: [read-only | read-write].
Operations: [list orgs/sites, list/get devices, list/get/update WLANs, …] + raw_request.

Description (for routing): Use when the user wants to query [or change] [PLATFORM]: [sites, APs, WLANs, clients,
events]. Only this specialist uses the [mist] MCP tools.
Tools: only `mcp__[mist]__*` (or your tool's equivalent), plus read/glob.

Rules:
- Read operations: run them and paste the results. Never invent IDs or values.
- Write operations:
  1. Show the exact change (object, field, old → new) and wait for "yes".
  2. Write.
  3. Read the object back and report the fields that prove it worked.
- Never print or ask for the token. If it is missing, tell me to set it in Settings → API tokens.

Build order:
1. Write the server, or register the existing one.
2. List its tools.
3. Run one read-only call and show me the result.
4. Only then enable writes.
5. Add the routing row and check the specialist appears in the UI.
6. Give me 3 test prompts.
````

## Add-on B: New specialist (optional; blank template)

````markdown
Add a new specialist to the Wi-Fi agent, following the same steps as the other specialists (Programmer script →
skill → specialist file → routing row → UI check → routing tests).

Key: [key]. Name: [Name]. Model tier: [fast | balanced | strongest].
Tools: [minimal list]. Skill: [skill-name] running [script.py <args>].
Description (for routing): Use when the user [exact triggers]. Does not [nearby jobs that belong to others].
Does: [3–6 bullets]. Does not: [3–6 bullets].
Script spec: inputs [..], arguments [..], output [Outputs/<name>_<job>.md], edge cases [..].
Sample file to test with: [upload it in the web chat first].
Routing tests: [2–3 prompts], plus one that must NOT route here.
````
