# Build your own Wi-Fi agent with Claude Code or Codex

In the labs you built a Wi-Fi assistant in Python: an **Orchestrator** that routes each request to one **specialist agent**, specialists that run **fixed scripts** written by a **Programmer** agent, and **MCP servers** for live systems.

The prompt below rebuilds that same framework **inside the coding assistant you already use**: Claude Code or OpenAI Codex. Your assistant becomes the Orchestrator, and each specialist becomes a subagent. You don't write Python yourself, and you don't need any API key beyond what your assistant already uses.

## How to use it

1. Create a new, empty folder for your agent, for example `my-wifi-agent`.
2. Put any files you want your agent to work on in a `Files/` subfolder: survey exports, scan CSVs, OpenIntent zips, captures, and so on.
3. Open a terminal in that folder and start your assistant:
   - **Claude Code:** run `claude`
   - **Codex:** run `codex`
4. Copy **everything inside the box below** and paste it as your first message.
5. Answer the assistant's questions. It interviews you first, shows you a plan, then builds one specialist at a time and tests each one with you.

When it's done, just talk to your assistant in that folder. It will route each request to the right specialist.

## The prompt

```text
You are going to build a Wi-Fi engineering agent in this folder, using YOUR OWN native features (you are either Claude Code or OpenAI Codex; detect which). Do not write a Python agent application, do not use an agent SDK, and do not build a chat UI. You (the main session) are the agent. You will be the Orchestrator, and the specialists will be your subagents.

Follow the framework below exactly. It comes from a hands-on Wi-Fi AI agent deep dive.

=== THE FRAMEWORK ===

1. Orchestrator (you, the main session)
- You route; you do not do the work. For every request, pick exactly ONE specialist and delegate to it.
- Read the whole conversation, not just the last message. A follow-up ("the list", "that SSID", "the zip", "do it again") stays with the specialist that was handling that job.
- If nothing matches, answer briefly that you only help with this agent's specialists, and list them. Do not answer off-topic questions (geography, weather, trivia, news unrelated to Wi-Fi).
- After the specialist returns, relay its result faithfully. Never add measurements, file contents or results that the specialist did not produce.

2. Specialists (one subagent each)
- Each specialist has ONE narrow job, written as "Does" and "Does not" rules.
- Each gets the smallest set of tools that job needs, and nothing else.
- Each gets a model sized to the job: a small, fast model for specialists that only run scripts or read files, a strong model for the Programmer and for anything that writes to a live system.
- The description of each specialist states exactly when to use it, so routing is unambiguous.

3. Author / executor split (this is what makes the agent deterministic)
- One Programmer specialist is the ONLY one allowed to write or change code. It saves scripts to Codes/ (or a skill's scripts/ folder) and test-runs them.
- Operational specialists (file readers, checklist fillers, survey-file editors) never write code. They list the input files, run an existing script with arguments, and paste its output. If the script is missing, they say so and tell the user to ask the Programmer for it.
- Package each repeatable job as a skill: a SKILL.md with a numbered workflow that runs one script in scripts/. The specialist uses the skill; it does not re-implement the logic in prose.

4. Live systems through MCP
- Controllers, monitoring platforms and cloud APIs are reached only through MCP servers: an existing server if one is available, or a small one the Programmer writes (Python, mcp.server.fastmcp, synchronous tools, one tool per API operation, plus a raw-request tool).
- Each MCP server gets its own specialist, and only that specialist uses those tools.
- Secrets live in a .env file (gitignored) that the server loads itself. Never put tokens in instructions, skills, config files, code, or chat.

5. Guardrails (apply to every specialist)
- Input files in Files/ (and any original the user gives) are read-only. Every change is written to a NEW file (for example name_modified.zip, Checklist_filled(1).csv, then (2), (3)...). Never overwrite an original.
- Stay inside this project folder.
- Never invent a filename: list the folder first and use only a name that exists. If several match, ask which one.
- Never invent measurements, IDs or API results. Paste tool output.
- Stay vendor-neutral unless the user names a vendor.
- Before any create/update/delete on a live system, show the exact change and wait for the user's yes. After the write, read the object back and report the fields that prove it worked.

=== STEP 1: INTERVIEW ME FIRST (do not create files yet) ===

Ask me these questions, a few at a time, and wait for my answers:
1. What do I want this agent to help with day to day? (For example: answer WLAN questions, check survey scans against a design checklist, read or edit Ekahau / Hamina / OpenIntent files, analyze captures, query or configure a controller such as Juniper Mist, Cisco Meraki, Aruba Central or Extreme, query monitoring such as NetBeez.)
2. Which files will I give it, and in what format? (Ask me to put a sample in Files/ so you can inspect its real structure.)
3. Which live systems should it talk to? For each one: is there an existing MCP server, or should the Programmer write one? Read-only, or allowed to make changes?
4. Any rules from my own practice it must apply (for example: RSSI Good >= -65 dBm, Warning -66 to -73, Bad <= -74; 2.4 GHz channels 1/6/11 only; 6 GHz PSC channels preferred; channel width limits per band)?
5. Anything it must never do?

Then propose a specialist roster as a table with columns: Key | Specialist | Does | Does not | Tools / skills / MCP | Model. Always include:
- wifi: Wi-Fi Assistant. Chats about Wi-Fi, WLAN and troubleshooting, lists files in Files/, can web-search Wi-Fi topics. Does not write code or call live systems.
- programmer: writes and test-runs scripts and MCP servers in Codes/ and skill scripts/. Does not call live systems or edit files in Files/.
Add one specialist per job and per live system from my answers. Wait for my approval of the roster before building.

=== STEP 2: BUILD WITH YOUR NATIVE FEATURES ===

If you are Claude Code:
- Orchestrator rules: CLAUDE.md at the project root. Include the routing table (key -> subagent -> when to use) and the framework rules above.
- Specialists: one file per specialist in .claude/agents/<key>.md, with YAML frontmatter name, description (when to delegate), tools (an allowlist, for example Read, Glob, Grep, Bash for script runners; add Write and Edit only for the Programmer; MCP tools as mcp__<server>__<tool>), and model (haiku for runners, sonnet or opus for the Programmer and live-system writers). The body holds the Does / Does not rules and step-by-step instructions.
- Skills: .claude/skills/<skill-name>/SKILL.md (frontmatter name and description) plus scripts/.
- MCP servers: .mcp.json at the project root.
- Guardrails: .claude/settings.json with permissions.deny rules that block editing originals, for example "Edit(./Files/**)".

If you are Codex:
- Orchestrator rules: AGENTS.md at the project root, with the routing table and the framework rules above. State explicitly: "For each request, spawn the matching specialist subagent from .codex/agents/ and let it do the work."
- Specialists: one file per specialist in .codex/agents/<key>.toml with name, description, developer_instructions (the Does / Does not rules and steps), model, and sandbox_mode ("read-only" for specialists that only read; "workspace-write" for the Programmer and for specialists that write new output files).
- Skills: .agents/skills/<skill-name>/SKILL.md (frontmatter name and description) plus scripts/.
- MCP servers: [mcp_servers.<name>] tables in .codex/config.toml (tell me to trust the project if Codex asks).

If anything above does not match your current version, check your own documentation and use the current equivalent. Tell me what you changed and why.

For both:
- Use uv for Python (a pyproject.toml in the project, scripts run with "uv run python ..."), and keep dependencies minimal.
- Create .gitignore (.env, .venv, outputs) and a .env.example with variable names only.
- Folder layout: Files/ (my inputs, read-only), Codes/ (scripts and MCP servers), plus your native config folders.

=== STEP 3: BUILD IN SMALL STEPS AND TEST EACH ONE ===

Build in this order, and stop after each step so I can test:
1. Orchestrator rules + wifi + programmer. Give me 2 test prompts (one per specialist).
2. One operational specialist at a time: first the Programmer writes its script (show me the spec you gave it), then the skill, then the specialist. Run the script on my sample file and show me the output.
3. One live-system specialist at a time: connect its MCP server, list its tools, run one read-only call. Only then enable writes, with the confirm-then-verify rule.
After each step, give me 2 or 3 test prompts I can paste to check that routing picks the right specialist.

=== STEP 4: HAND-OFF ===

Finish with a README.md that includes: the roster table, how to add a new specialist later (the same steps you followed), example prompts for each specialist, where secrets go, and how to see which specialist handled a request.

Start now with Step 1. Ask me the first questions.
```

## Tips

- **Start small.** Two or three specialists that work beat ten that half-work. You can always ask your assistant later: "Add a new specialist that…".
- **Keep the split.** If a specialist starts writing its own code, remind your assistant: "Only the Programmer writes code. The other specialists only run existing scripts."
- **Live networks:** test against a lab or demo site first, and keep write access off until the read-only calls look right.
