"""Chat box for the vibe-coding lab.

One builder. Students pick OpenAI or Ollama before each message, then ask
the chat to create an agent and its sub-agents, change an agent that already
exists, or write a skill folder. Agents stay in this chat. Skills are folders
under Skills/.
"""

from __future__ import annotations

import asyncio
import base64
import contextvars
import json
import mimetypes
import os
import re
import shlex
import shutil
import struct
import subprocess
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

import gradio as gr
from agents import Agent, OpenAIChatCompletionsModel, Runner, function_tool, set_tracing_disabled
from agents.mcp import MCPServerStdio
from agents.model_settings import ModelSettings
from dotenv import load_dotenv
from openai import AsyncOpenAI
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[2]
LAB = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
UPLOADS = LAB / "Uploads"
CODES_DIR = LAB / "Codes"
SKILLS_DIR = LAB / "Skills"
REGISTRY = HERE / "built_agents.json"

load_dotenv(ROOT / ".env", override=True)

PROVIDERS = ["OpenAI", "Ollama"]
OPENAI_MODELS = [
    "gpt-5.4-mini",
    "gpt-5.4",
    "gpt-5.4-pro",
    "gpt-5.5",
    "gpt-5.5-pro",
    "gpt-5.6-sol",
    "gpt-6-sol",
    "gpt-6-astra",
]
OLLAMA_MODEL = "qwen2.5:7b"
MAX_CHARS = 8_000
MAX_IMAGE_BYTES = 4_000_000

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
CAPTURE_SUFFIXES = {".pcap", ".pcapng"}
BINARY_SUFFIXES = {".esx", ".zip", ".gz"}

INSTRUCTIONS = """
You are the AI Assistant for this chat. The student talks to you to build agents, skills, and MCP servers, and to write and run Python.
When asked who you are, say: I'm your AI Assistant for this chat.
A skill is a folder, not an agent. When the student asks for a skill, call save_skill. Do not call create_agent.

How to build:
- Call create_agent for the main agent first. Leave parent empty.
- Call create_agent once for each sub-agent. Set parent to the main agent's name.
- Set can_code true only when that agent must write or run Python.
- Then call list_agents and tell the student the tree in a few lines.
- An agent you create in this turn is available on the next message. Do not call it yet.

How to change an agent that already exists:
- Call get_agent first and keep every behavior the student did not mention.
- Call update_agent for a new name, new instructions, a new parent, or can_code.
- Leave a field empty to keep it. Pass parent as "-" only to make a top-level agent.
- Pass can_code as "true" or "false" only when that should change.
- Add a new sub-agent with create_agent. Do not use create_agent to edit an existing one.
- The edited agent is used on the next message. Say that in one line.

How to build a skill:
- Call save_skill. The folder is Skills/<name>/SKILL.md.
- name is lowercase words with hyphens, such as wifi-explorer-ssid.
- description says what the skill does and when to use it, in third person.
- skill_markdown is the body only: a title, the job, a numbered workflow, and rules.
- Put the fragile work in scripts/<script>.py. The workflow runs that script and does not parse the file another way.
- The command, from the lab folder, is python3 Skills/<name>/scripts/<script>.py.
- In that script, the lab folder is Path(__file__).resolve().parents[3]. Stay inside it.
- Put long tables in a reference file such as columns.md and link it from SKILL.md.
- Tell the student the folder path save_skill prints.

How to build an MCP server:
- Call save_python_code and save the server as one .py file in Codes/.
- A server saved during this message is connected on the next message.

How to use a skill:
- Call read_skill, then run_skill_script with the arguments the skill names.
- Paste the script output. Do not reimplement the script.

How to use what you built:
- If an agent is already one of your tools and the request matches that agent, call it now. Do not call create_agent again.
- That agent calls its own sub-agents. Do not do a sub-agent's job yourself when that sub-agent exists.
- When the student asks you to write or run Python, call save_python_code and then run_saved_python yourself, then paste the output. Do this even when a coding agent exists.
- A graph is a picture of the capture, in the style of an example image the student attaches. The example is style only. The numbers come from a pcap in this conversation.
- When a capture is in the conversation and the student asks for a graph or diagram, call read_capture. If the student names a transmitter MAC, pass that mac. Then call save_python_code and run_saved_python. Plot the rows under "Data frames over time" from that reading: time on the x axis, sent and retries as two series. Save a .png. The picture is shown under your reply. Do not draw the graph as text. Do not invent the numbers.
- If the reading contains "Data frames transmitted by", that sent and retries pair is the count for that transmitter. Do not use the broader Retries line.
- If no capture is in the conversation, ask the student to attach the pcap here. Do not tell them to open Wireshark or run tshark.
- When an MCP server is connected, call its tools yourself. Do not run that file with run_saved_python.
- Do not tell the student to run Python, start a server, or paste output back.
- Paste the tool output. Do not invent file contents, measurements, or program output.

Captures:
- A pcap or pcapng attached in chat is already read. The reading is in the message.
- Call read_capture yourself for another pass, or pass mac when the student names a device.
- If a capture agent exists, call that agent. It reads the file.
- Never tell the student to run Wireshark, tshark, tcpdump, Python, or any command. Never hand them a script.

The earlier messages are this conversation. Use them on a follow-up. Do not ask the student to repeat a request they already made.
Never print API keys or tokens.
""".strip()

_NEW_IMAGES: contextvars.ContextVar[list[str] | None] = contextvars.ContextVar("new_images", default=None)


def _image_stamps() -> dict[str, int]:
    stamps: dict[str, int] = {}
    if not LAB.is_dir():
        return stamps
    for path in LAB.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in IMAGE_SUFFIXES:
            continue
        if any(part.startswith(".") or part == "__pycache__" for part in path.relative_to(LAB).parts):
            continue
        try:
            stamps[str(path.resolve())] = path.stat().st_mtime_ns
        except OSError:
            continue
    return stamps


def _keep_new_images(before: dict[str, int]) -> None:
    bucket = _NEW_IMAGES.get()
    if bucket is None:
        return
    for path, stamp in _image_stamps().items():
        if before.get(path) != stamp and path not in bucket:
            bucket.append(path)


_mcp_lock = asyncio.Lock()
_mcp_servers: dict[str, tuple[int, MCPServerStdio]] = {}

ollama_client = AsyncOpenAI(
    base_url="http://127.0.0.1:11434/v1",
    api_key="ollama",
)


def backend_of(provider: str) -> str:
    return "ollama" if provider.strip().lower() == "ollama" else "openai"


@function_tool
def list_workspace() -> str:
    """List Python files in Codes/ and uploaded files in Uploads/."""

    def lines(folder: Path) -> str:
        if not folder.is_dir():
            return f"{folder.name}/ is missing."
        files = sorted(p for p in folder.iterdir() if p.is_file() and not p.name.startswith("."))
        if not files:
            return f"{folder.name}/ is empty."
        return "\n".join(f"{folder.name}/{p.name} ({p.stat().st_size} bytes)" for p in files)

    return lines(CODES_DIR) + "\n" + lines(UPLOADS)


@function_tool
def save_python_code(filename: str, code: str) -> str:
    """Save Python code into the Codes folder.

    filename: a short .py name, for example wifi_scan.py
    code: the full Python source to write
    """
    CODES_DIR.mkdir(parents=True, exist_ok=True)
    name = Path(filename).name
    if not name.endswith(".py"):
        name = name + ".py"
    path = CODES_DIR / name
    path.write_text(code, encoding="utf-8")
    print(f"Saved Python code to {path}")
    return f"Saved {path}"


@function_tool
def run_saved_python(filename: str, extra_args: str = "") -> str:
    """Run a .py file from the Codes folder and return stdout/stderr.

    filename: the file name only, for example wifi_scan.py
    extra_args: optional CLI args
    """
    name = Path(filename).name
    if not name.endswith(".py"):
        name = name + ".py"
    path = (CODES_DIR / name).resolve()
    if path.parent != CODES_DIR.resolve():
        return "Refusing to run a file outside Codes/"
    if not path.is_file():
        return f"No such file: {path}"
    if is_mcp_server(path):
        return f"{name} is an MCP server and is already connected. Call its tools. Do not run this file."
    extra = shlex.split(extra_args) if extra_args.strip() else []
    before = _image_stamps()
    try:
        completed = subprocess.run(
            [sys.executable, str(path), *extra],
            capture_output=True,
            text=True,
            timeout=90,
            cwd=str(LAB),
            env={**os.environ},
        )
    except subprocess.TimeoutExpired:
        _keep_new_images(before)
        return "The program ran longer than 90 seconds and was stopped."
    _keep_new_images(before)
    out = (completed.stdout or "") + (completed.stderr or "")
    return f"exit_code={completed.returncode}\n{out[-4000:]}"


CAPTURE_RULE = (
    "\n\npcap and pcapng files in Uploads/ are readable. "
    "Call read_capture with the file name. Pass mac when the student names a device. "
    "Answer from that result. The data-frame rows over time are included. "
    "Never tell the student to run Wireshark, tshark, tcpdump, "
    "Python, or any command, and never hand them a script to run."
)

_PCAP_MAGIC = {
    0xA1B2C3D4: (">", 1_000_000),
    0xD4C3B2A1: ("<", 1_000_000),
    0xA1B23C4D: (">", 1_000_000_000),
    0x4D3CB2A1: ("<", 1_000_000_000),
}
_KINDS = ("Mgmt", "Ctrl", "Data", "Ext")
_SUBTYPES = {
    (0, 0): "Assoc Req",
    (0, 1): "Assoc Resp",
    (0, 4): "Probe Req",
    (0, 5): "Probe Resp",
    (0, 8): "Beacon",
    (0, 10): "Disassoc",
    (0, 11): "Auth",
    (0, 12): "Deauth",
    (0, 13): "Action",
    (1, 8): "Block Ack Req",
    (1, 9): "Block Ack",
    (1, 10): "PS-Poll",
    (1, 11): "RTS",
    (1, 12): "CTS",
    (1, 13): "ACK",
    (2, 0): "Data",
    (2, 4): "Null",
    (2, 8): "QoS Data",
    (2, 12): "QoS Null",
}
_RT_FIELDS = ((8, 8), (1, 1), (1, 1), (2, 4), (2, 2), (1, 1))
_CAPTURE_CACHE: dict[tuple, str] = {}


def _norm_mac(value: str) -> str | None:
    raw = "".join(ch for ch in value.lower() if ch in "0123456789abcdef")
    if len(raw) != 12:
        return None
    return ":".join(raw[i : i + 2] for i in range(0, 12, 2))


def _mac(buf, index: int) -> str | None:
    if index < 0 or index + 6 > len(buf):
        return None
    return ":".join(f"{buf[index + i]:02x}" for i in range(6))


def _radiotap_signal(pkt) -> int | None:
    if len(pkt) < 8:
        return None
    it_len = struct.unpack_from("<H", pkt, 2)[0]
    if it_len < 8 or it_len > len(pkt):
        return None
    present: list[int] = []
    pos = 4
    while pos + 4 <= it_len and len(present) < 8:
        word = struct.unpack_from("<I", pkt, pos)[0]
        present.append(word)
        pos += 4
        if not word & 0x80000000:
            break
    if not present or not present[0] & (1 << 5):
        return None
    offset = pos
    for bit, (align, size) in enumerate(_RT_FIELDS):
        if not present[0] & (1 << bit):
            continue
        offset = (offset + align - 1) & ~(align - 1)
        if offset + size > it_len:
            return None
        if bit == 5:
            value = int(pkt[offset])
            return value - 256 if value >= 128 else value
        offset += size
    return None


def _idb_info(mv: memoryview, off: int, block_len: int, endian: str) -> tuple[int, float]:
    link = struct.unpack_from(endian + "H", mv, off + 8)[0]
    tick = 1_000_000.0
    pos = off + 16
    end = off + block_len - 4
    while pos + 4 <= end:
        code, length = struct.unpack_from(endian + "HH", mv, pos)
        pos += 4
        if code == 0:
            break
        if code == 9 and length >= 1 and pos < end:
            res = int(mv[pos])
            if res & 0x80:
                tick = float(1 << (res & 0x7F))
            elif res:
                tick = float(10 ** (res & 0x7F))
        pos += (length + 3) & ~3
    return link, tick


def _iter_pcapng(mv: memoryview):
    off = 0
    endian = "<"
    ifaces: list[tuple[int, float]] = []
    limit = len(mv)
    while off + 12 <= limit:
        block_type = struct.unpack_from(endian + "I", mv, off)[0]
        block_len = struct.unpack_from(endian + "I", mv, off + 4)[0]
        if block_type == 0x0A0D0D0A and off + 12 <= limit:
            bom = struct.unpack_from("<I", mv, off + 8)[0]
            if bom == 0x1A2B3C4D:
                endian = "<"
            elif bom == 0x4D3C2B1A:
                endian = ">"
            block_len = struct.unpack_from(endian + "I", mv, off + 4)[0]
            ifaces = []
        if block_len < 12 or off + block_len > limit:
            break
        if block_type == 1 and block_len >= 16:
            ifaces.append(_idb_info(mv, off, block_len, endian))
        elif block_type == 6 and block_len >= 28:
            iface, ts_hi, ts_lo, caplen, _pktlen = struct.unpack_from(endian + "IIIII", mv, off + 8)
            start = off + 28
            if 0 <= caplen and start + caplen <= off + block_len:
                link, tick = ifaces[iface] if 0 <= iface < len(ifaces) else (127, 1_000_000.0)
                ts = ((ts_hi << 32) | ts_lo) / tick
                yield link, ts, mv[start : start + caplen]
        elif block_type == 3 and block_len >= 16:
            pktlen = struct.unpack_from(endian + "I", mv, off + 8)[0]
            start = off + 12
            link = ifaces[0][0] if ifaces else 1
            if start + pktlen <= off + block_len:
                yield link, None, mv[start : start + pktlen]
        off += block_len


def _iter_packets(path: Path):
    mv = memoryview(path.read_bytes())
    if len(mv) < 24:
        raise ValueError("file is too small to be a capture")
    magic = struct.unpack_from(">I", mv, 0)[0]
    if magic == 0x0A0D0D0A:
        yield from _iter_pcapng(mv)
        return
    spec = _PCAP_MAGIC.get(magic)
    if spec is None:
        raise ValueError("not a pcap or pcapng file")
    endian, tick = spec
    link = struct.unpack_from(endian + "I", mv, 20)[0]
    off = 24
    limit = len(mv)
    while off + 16 <= limit:
        ts_sec, ts_frac, incl, _orig = struct.unpack_from(endian + "IIII", mv, off)
        off += 16
        if incl > 1_000_000 or off + incl > limit:
            break
        yield link, ts_sec + (ts_frac / tick), mv[off : off + incl]
        off += incl


def _frame_name(kind: int, subtype: int) -> str:
    label = _KINDS[kind] if kind < len(_KINDS) else str(kind)
    name = _SUBTYPES.get((kind, subtype))
    return f"{label} / {name}" if name else f"{label} {kind}/{subtype}"


def _clock(ts: float | None) -> str:
    if ts is None:
        return "unknown"
    when = datetime.fromtimestamp(ts)
    if when.year < 2000 or when.year > 2100:
        return f"{ts:.3f}"
    return when.strftime("%Y-%m-%d %H:%M:%S")


def _per_second_lines(per_second: dict[int, list[int]]) -> list[str]:
    """Rows the model can plot: time, data frames sent, data frames with the retry bit."""
    if not per_second:
        return []
    start, end = min(per_second), max(per_second)
    span = end - start + 1
    step = 1
    for candidate in (1, 2, 5, 10, 30, 60):
        if span / candidate <= 200:
            step = candidate
            break
    else:
        step = max(1, (span + 199) // 200)
    window = "one second" if step == 1 else f"{step} seconds"
    lines = [
        "Data frames over time. Columns: time, sent, retries. "
        f"Retries are data frames with the retry bit. Each row is {window}."
    ]
    cursor = start
    while cursor <= end:
        sent = retries = 0
        for sec in range(cursor, min(cursor + step, end + 1)):
            pair = per_second.get(sec)
            if pair:
                sent += pair[0]
                retries += pair[1]
        when = datetime.fromtimestamp(cursor).strftime("%H:%M:%S")
        lines.append(f"{when} {sent} {retries}")
        cursor += step
    return lines


def summarize_capture(path: Path, mac: str = "") -> str:
    """Read a pcap or pcapng and return a short Wi-Fi / packet summary."""
    target = ""
    if mac.strip():
        target = _norm_mac(mac) or ""
        if not target:
            return "MAC addresses look like aa:bb:cc:dd:ee:ff."
    total = matched = 0
    first_ts = last_ts = None
    kinds: Counter[str] = Counter()
    retries = protected = decoded = other = 0
    transmitters: Counter[str] = Counter()
    receivers: Counter[str] = Counter()
    bssids: Counter[str] = Counter()
    signals: Counter[int] = Counter()
    per_second: dict[int, list[int]] = {}
    ta_per_second: dict[int, list[int]] = {}
    ta_sent = ta_retries = 0
    link_counts: Counter[int] = Counter()
    for link, ts, pkt in _iter_packets(path):
        total += 1
        link_counts[link] += 1
        if ts is not None:
            first_ts = ts if first_ts is None else min(first_ts, ts)
            last_ts = ts if last_ts is None else max(last_ts, ts)
        start = 0
        if link == 127:
            if len(pkt) < 4:
                other += 1
                continue
            start = struct.unpack_from("<H", pkt, 2)[0]
            if start < 8 or start + 2 > len(pkt):
                other += 1
                continue
        elif link == 105:
            start = 0
            if len(pkt) < 2:
                other += 1
                continue
        else:
            other += 1
            continue
        fc0 = int(pkt[start])
        fc1 = int(pkt[start + 1])
        kind = (fc0 >> 2) & 0x3
        subtype = (fc0 >> 4) & 0xF
        addr1 = _mac(pkt, start + 4)
        has_addr2 = not (kind == 1 and subtype in (12, 13))
        addr2 = _mac(pkt, start + 10) if has_addr2 else None
        addr3 = _mac(pkt, start + 16) if kind in (0, 2) else None
        if target and target not in (addr1, addr2, addr3):
            continue
        matched += 1
        decoded += 1
        kinds[_frame_name(kind, subtype)] += 1
        if fc1 & 0x08:
            retries += 1
        if fc1 & 0x40:
            protected += 1
        if addr1:
            receivers[addr1] += 1
        if addr2:
            transmitters[addr2] += 1
        bssid = None
        if kind == 0:
            bssid = addr3
        elif kind == 2:
            to_ds = bool(fc1 & 0x01)
            from_ds = bool(fc1 & 0x02)
            if to_ds and not from_ds:
                bssid = addr1
            elif from_ds and not to_ds:
                bssid = addr2
            elif not to_ds and not from_ds:
                bssid = addr3
        if bssid:
            bssids[bssid] += 1
        if link == 127:
            signal = _radiotap_signal(pkt)
            if signal is not None and -110 <= signal <= 0:
                signals[signal] += 1
        if kind == 2 and not subtype & 0x4 and ts is not None and not target:
            slot = per_second.setdefault(int(ts), [0, 0])
            slot[0] += 1
            if fc1 & 0x08:
                slot[1] += 1
        if kind == 2 and target and addr2 == target and ts is not None:
            ta_sent += 1
            if fc1 & 0x08:
                ta_retries += 1
            slot = ta_per_second.setdefault(int(ts), [0, 0])
            slot[0] += 1
            if fc1 & 0x08:
                slot[1] += 1
    if total == 0:
        return f"{path.name} has no packets."
    span = ""
    if first_ts is not None and last_ts is not None:
        span = f" from {_clock(first_ts)} to {_clock(last_ts)} ({last_ts - first_ts:.1f}s)"
    focus = f", frames with {target}: {matched}" if target else ""
    lines = [
        f"{path.name}: {total} packets{span}{focus}.",
    ]
    if other and not decoded:
        links = ", ".join(f"{link} x{count}" for link, count in link_counts.most_common(4))
        lines.append(f"Link types: {links}. Frame headers were not 802.11, so only the packet count is shown.")
        return "\n".join(lines)
    if decoded:
        scope = f" involving {target}" if target else ""
        lines.append(
            f"802.11 frames{scope}: {decoded}. "
            f"Retries: {retries} ({100 * retries / decoded:.1f}%). Protected: {protected}."
        )
        if target:
            lines.append(
                f"Data frames transmitted by {target}: sent {ta_sent}, retries {ta_retries}. "
                "This is 802.11 type 2 with transmitter address equal to that MAC, "
                "and retries are those with the retry bit set. "
                "Use this count. The Retries line above also includes other frame types and other transmitters."
            )
            lines.extend(_per_second_lines(ta_per_second))
        else:
            lines.extend(_per_second_lines(per_second))
        lines.append("Frames:")
        for name, count in kinds.most_common(12):
            lines.append(f"  {name}: {count}")
        lines.append("Transmitters:")
        for name, count in transmitters.most_common(8):
            lines.append(f"  {name}: {count}")
        lines.append("Receivers:")
        for name, count in receivers.most_common(8):
            lines.append(f"  {name}: {count}")
        if bssids:
            lines.append("BSSIDs:")
            for name, count in bssids.most_common(6):
                lines.append(f"  {name}: {count}")
        if signals:
            ordered = sorted(signals)
            running = 0
            half = sum(signals.values()) / 2
            median = ordered[-1]
            for value in ordered:
                running += signals[value]
                if running >= half:
                    median = value
                    break
            lines.append(f"Signal dBm: min {ordered[0]}, median {median}, max {ordered[-1]}.")
    text = "\n".join(lines)
    if len(text) > 14000:
        text = text[:14000] + "\n[summary truncated]"
    return text


def cached_summary(path: Path, mac: str = "") -> str:
    wanted = ""
    if mac.strip():
        wanted = _norm_mac(mac) or ""
        if not wanted:
            return "MAC addresses look like aa:bb:cc:dd:ee:ff."
    stat = path.stat()
    key = (str(path.resolve()), stat.st_mtime_ns, stat.st_size, wanted)
    hit = _CAPTURE_CACHE.get(key)
    if hit is not None:
        return hit
    text = summarize_capture(path, wanted)
    _CAPTURE_CACHE[key] = text
    return text


def find_upload(filename: str) -> Path:
    name = Path(filename.strip().strip('"').strip("'")).name
    uploads = UPLOADS.resolve()
    direct = (uploads / name).resolve()
    if direct.parent != uploads:
        raise ValueError("That file is outside Uploads/.")
    if direct.is_file():
        return direct
    folded = name.casefold()
    matches = [item for item in uploads.iterdir() if item.is_file() and item.name.casefold() == folded]
    if len(matches) == 1:
        return matches[0]
    names = sorted(item.name for item in uploads.iterdir() if item.is_file() and item.suffix.lower() in CAPTURE_SUFFIXES)
    hint = ", ".join(names[:12]) if names else "Uploads/ has no captures."
    raise ValueError(f"No capture named {name}. Available: {hint}")


@function_tool
def read_capture(filename: str, mac: str = "") -> str:
    """Read a Wireshark capture saved in Uploads/ and return what is in it.

    filename: the file name only, such as capture.pcap or capture.pcapng
    mac: optional device address, such as aa:bb:cc:dd:ee:ff. Leave empty for the whole file.
    """
    try:
        path = find_upload(filename)
    except ValueError as exc:
        return str(exc)
    if path.suffix.lower() not in CAPTURE_SUFFIXES:
        return f"{path.name} is not a pcap or pcapng file."
    try:
        return cached_summary(path, mac)
    except Exception as exc:
        return f"Could not read {path.name}: {type(exc).__name__}: {exc}"


def load_registry() -> list[dict]:
    if not REGISTRY.is_file():
        return []
    try:
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    agents = data.get("agents", [])
    return agents if isinstance(agents, list) else []


def save_registry(agents: list[dict]) -> None:
    REGISTRY.write_text(json.dumps({"agents": agents}, indent=2), encoding="utf-8")


def slug(name: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "_" for ch in name.strip())
    parts = [part for part in cleaned.split("_") if part]
    return "_".join(parts) or "agent"


def find_agent(agents: list[dict], name: str) -> dict | None:
    wanted = name.strip().lower()
    for record in agents:
        if str(record.get("name", "")).strip().lower() == wanted:
            return record
    return None


def skill_folder_name(name: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
    return text[:64].strip("-")


def skill_names() -> list[str]:
    if not SKILLS_DIR.is_dir():
        return []
    names = []
    for path in sorted(SKILLS_DIR.iterdir()):
        if path.is_dir() and not path.name.startswith(".") and (path / "SKILL.md").is_file():
            names.append(path.name)
    return names


def agent_tree() -> str:
    agents = load_registry()
    lines = []
    if not agents:
        lines.append("No agents yet.")
    tops = [record for record in agents if not str(record.get("parent", "")).strip()]
    children = [record for record in agents if str(record.get("parent", "")).strip()]
    shown = set()

    def write(record: dict, indent: str) -> None:
        name = str(record.get("name", "")).strip()
        shown.add(name.lower())
        code = " · writes Python" if record.get("can_code") else ""
        lines.append(f"{indent}{name}{code}")
        for child in children:
            if str(child.get("parent", "")).strip().lower() == name.lower():
                write(child, indent + "  ")

    for record in tops:
        write(record, "")
    for record in children:
        if str(record.get("name", "")).strip().lower() not in shown:
            write(record, "")
    lines.append("")
    skills = skill_names()
    if skills:
        lines.append("Skills")
        lines.extend(f"  {name}" for name in skills)
    else:
        lines.append("No skills yet.")
    if not agents and not skills:
        lines.extend(["", "Ask the chat to build an agent or a skill."])
    return "\n".join(lines)


@function_tool
def create_agent(name: str, instructions: str, parent: str = "", can_code: bool = False) -> str:
    """Add an agent to this chat, or replace it if the name already exists.

    name: short display name, for example Wi-Fi Assistant
    instructions: what this agent does and what it must not do
    parent: exact name of the parent agent. Leave empty for the main agent. Set it for a sub-agent.
    can_code: true only if this agent must save and run Python
    """
    title = " ".join(name.split()).strip()
    body = instructions.strip()
    parent_name = " ".join(parent.split()).strip()
    if len(title) < 2:
        return "Name is too short."
    if len(body) < 20:
        return "Instructions are too short. Say what the agent does and what it must not do."
    agents = load_registry()
    if parent_name and find_agent(agents, parent_name) is None:
        return f"No parent named {parent_name}. Create that agent first, with an empty parent."
    if parent_name.lower() == title.lower():
        return "An agent cannot be its own parent."
    cursor = parent_name
    seen = {title.lower()}
    while cursor:
        key = cursor.strip().lower()
        if key in seen:
            return "That parent would make a loop. Pick a parent above this agent."
        seen.add(key)
        parent_record = find_agent(agents, cursor)
        cursor = str(parent_record.get("parent", "")).strip() if parent_record else ""
    existing = find_agent(agents, title)
    record = {
        "name": title,
        "instructions": body[:4000],
        "parent": parent_name,
        "can_code": bool(can_code),
    }
    if existing is None:
        agents.append(record)
        verb = "Created"
    else:
        existing.update(record)
        verb = "Updated"
    save_registry(agents)
    kind = "sub-agent" if parent_name else "agent"
    parent_note = f" under {parent_name}" if parent_name else ""
    print(f"{verb} {kind}: {title}{parent_note}")
    if verb == "Updated":
        return (
            f"Updated {kind} {title}{parent_note}. "
            "This turn still uses the previous version. The new version is used on the next message."
        )
    return f"Created {kind} {title}{parent_note}. It can be used on the next message, not in this turn."


def _flag(value: str) -> bool | None | str:
    text = value.strip().lower()
    if text in {"", "keep", "unchanged"}:
        return None
    if text in {"true", "yes", "1"}:
        return True
    if text in {"false", "no", "0"}:
        return False
    return "can_code must be true, false, or empty to keep the current setting."


def get_agent(name: str) -> str:
    """Return one agent's name, parent, coding flag, sub-agents, and full instructions.

    name: the agent to read
    """
    agents = load_registry()
    record = find_agent(agents, name)
    if record is None:
        return f"No agent named {name.strip()}."
    title = str(record.get("name", "")).strip()
    parent = str(record.get("parent", "")).strip() or "(none)"
    kids = [
        str(other.get("name", "")).strip()
        for other in agents
        if str(other.get("parent", "")).strip().lower() == title.lower()
    ]
    body = str(record.get("instructions", "")).strip()
    return (
        f"name: {title}\n"
        f"parent: {parent}\n"
        f"can_code: {'true' if record.get('can_code') else 'false'}\n"
        f"sub-agents: {', '.join(kids) if kids else '(none)'}\n"
        f"instructions:\n{body}"
    )


def update_agent(
    name: str,
    instructions: str = "",
    new_name: str = "",
    parent: str = "",
    can_code: str = "",
) -> str:
    """Change an agent that already exists. Does not create one.

    name: the agent to change, as listed
    instructions: replacement instructions. Empty keeps the current instructions.
    new_name: new display name. Empty keeps the current name.
    parent: new parent name. Empty keeps the current parent. "-" makes this a top-level agent.
    can_code: "true" or "false". Empty keeps the current setting.
    """
    agents = load_registry()
    record = find_agent(agents, name)
    if record is None:
        return f"No agent named {name.strip()}. Call list_agents to see the names."

    current_name = str(record.get("name", "")).strip()
    current_key = current_name.lower()
    title = current_name
    if new_name.strip() and new_name.strip().lower() not in {"keep", "unchanged"}:
        title = " ".join(new_name.split()).strip()
        if len(title) < 2:
            return "Name is too short."
        taken = find_agent(agents, title)
        if taken is not None and taken is not record:
            return f"An agent named {title} already exists."

    if not instructions.strip() or instructions.strip().lower() in {"keep", "unchanged"}:
        body = str(record.get("instructions", "")).strip()
    else:
        body = instructions.strip()
        if len(body) < 20:
            return "Instructions are too short. Say what the agent does and what it must not do."
        body = body[:4000]

    parent_text = parent.strip()
    if parent_text in {"", "keep", "unchanged"}:
        parent_name = str(record.get("parent", "")).strip()
    elif parent_text == "-":
        parent_name = ""
    else:
        parent_name = " ".join(parent_text.split()).strip()
        if find_agent(agents, parent_name) is None:
            return f"No parent named {parent_name}."

    flag = _flag(can_code)
    if isinstance(flag, str):
        return flag
    if flag is None:
        flag = bool(record.get("can_code"))

    if parent_name.lower() in {current_key, title.lower()}:
        return "An agent cannot be its own parent."
    cursor = parent_name
    seen = set()
    while cursor:
        key = cursor.strip().lower()
        if key in {current_key, title.lower()} or key in seen:
            return "That parent would make a loop. Pick a parent above this agent."
        seen.add(key)
        parent_record = find_agent(agents, cursor)
        cursor = str(parent_record.get("parent", "")).strip() if parent_record else ""

    same = (
        title == current_name
        and body == str(record.get("instructions", "")).strip()
        and parent_name == str(record.get("parent", "")).strip()
        and flag == bool(record.get("can_code"))
    )
    if same:
        return f"{current_name} is unchanged."

    if title.lower() != current_key:
        for other in agents:
            if other is record:
                continue
            if str(other.get("parent", "")).strip().lower() == current_key:
                other["parent"] = title
    record["name"] = title
    record["instructions"] = body
    record["parent"] = parent_name
    record["can_code"] = flag
    save_registry(agents)
    kind = "sub-agent" if parent_name else "agent"
    parent_note = f" under {parent_name}" if parent_name else ""
    print(f"Updated {kind}: {title}{parent_note}")
    return (
        f"Updated {kind} {title}{parent_note}.\n"
        f"{get_agent(title)}\n"
        "This turn still uses the previous version. The new version is used on the next message."
    )


get_agent_tool = function_tool(get_agent)
update_agent_tool = function_tool(update_agent)


def _inside(path: Path, root: Path) -> bool:
    resolved = path.resolve()
    base = root.resolve()
    return resolved == base or base in resolved.parents


def _split_skill(text: str) -> tuple[str, str]:
    body = text.strip()
    if not body.startswith("---"):
        return "", body
    end = body.find("\n---", 3)
    if end < 0:
        return "", body
    header = body[3:end]
    rest = body[end + 4 :].strip()
    folded = re.search(r"^description:\s*>-\s*\n((?:[ \t].*\n?)*)", header, re.M)
    if folded:
        lines = [line.strip() for line in folded.group(1).splitlines()]
        description = " ".join(line for line in lines if line)
    else:
        quoted = re.search(r'^description:\s*"(.*)"\s*$', header, re.M)
        if quoted:
            description = quoted.group(1).replace('\\"', '"').replace("\\\\", "\\")
        else:
            plain = re.search(r"^description:\s*(.+)$", header, re.M)
            description = plain.group(1).strip() if plain else ""
    return description, rest


def _yaml_description(text: str) -> str:
    cleaned = " ".join(text.split())
    if len(cleaned) > 1024:
        cleaned = cleaned[:1024].rstrip()
    lines: list[str] = []
    current = ""
    for word in cleaned.split(" "):
        piece = word if not current else f"{current} {word}"
        if len(piece) > 78 and current:
            lines.append(current)
            current = word
        else:
            current = piece
    if current:
        lines.append(current)
    folded = "\n".join(f"  {line}" for line in lines)
    return f"description: >-\n{folded}"


def _from_lab(path: Path) -> str:
    try:
        return str(path.relative_to(LAB))
    except ValueError:
        return str(path)


def _skill_dir(name: str) -> Path | str:
    folder = skill_folder_name(name)
    if len(folder) < 2:
        return "Skill name needs letters or numbers. Use a name such as wifi-explorer-ssid."
    path = (SKILLS_DIR / folder).resolve()
    if path.parent != SKILLS_DIR.resolve():
        return "Skill path is outside Skills/."
    return path


def _script_file(folder: Path, filename: str) -> Path | str:
    name = Path(filename).name
    if not name.endswith(".py"):
        name += ".py"
    if name.startswith(".") or name == ".py":
        return "Script name must be a .py file name, such as filter_ssid.py."
    dest = (folder / "scripts" / name).resolve()
    if not _inside(dest, folder / "scripts"):
        return "Script path is outside the skill."
    return dest


def _reference_file(folder: Path, filename: str) -> Path | str:
    name = Path(filename).name
    if not name.endswith(".md"):
        name += ".md"
    if name.lower() == "skill.md" or name.startswith("."):
        return "Put the skill body in skill_markdown. A reference file needs another name, such as columns.md."
    dest = (folder / name).resolve()
    if dest.parent != folder.resolve():
        return "A reference file sits next to SKILL.md."
    return dest


def save_skill(
    name: str,
    description: str = "",
    skill_markdown: str = "",
    script_filename: str = "",
    script_code: str = "",
    reference_filename: str = "",
    reference_markdown: str = "",
) -> str:
    """Write a skill folder under Skills/, matching a SKILL.md plus optional script and notes.

    name: hyphenated folder name, such as wifi-explorer-ssid
    description: what the skill does and when to use it
    skill_markdown: SKILL.md body without the YAML header. Title, workflow, and rules.
    script_filename: optional script file name, such as filter_ssid.py
    script_code: full Python for that script. Empty leaves existing scripts unchanged.
    reference_filename: optional notes file, such as columns.md
    reference_markdown: markdown for that notes file. Empty leaves it unchanged.
    """
    folder = _skill_dir(name)
    if isinstance(folder, str):
        return folder
    existing = folder / "SKILL.md"
    old_description, old_body = ("", "")
    if existing.is_file():
        old_description, old_body = _split_skill(existing.read_text(encoding="utf-8"))

    description_text = " ".join(description.split())
    if not description_text or description_text.lower() in {"keep", "unchanged"}:
        description_text = old_description
    if len(description_text) < 20:
        return "Description is too short. Say what the skill does and when to use it."
    if len(description_text) > 1024:
        description_text = description_text[:1024].rstrip()

    body = skill_markdown.strip()
    if body.lower() in {"keep", "unchanged"}:
        body = ""
    if body.startswith("---"):
        _, body = _split_skill(body)
    if not body:
        body = old_body
    if len(body) < 80:
        return "Skill text is too short. Include the job, a numbered workflow, and the rules."

    script: Path | None = None
    if script_filename.strip() or script_code.strip():
        if not script_code.strip():
            return "Script code is empty. Pass the full Python source in script_code."
        script = _script_file(folder, script_filename or "run.py")
        if isinstance(script, str):
            return script

    notes: Path | None = None
    if reference_filename.strip() or reference_markdown.strip():
        if len(reference_markdown.strip()) < 20:
            return "Reference text is too short."
        notes = _reference_file(folder, reference_filename or "reference.md")
        if isinstance(notes, str):
            return notes

    written: list[Path] = []
    folder.mkdir(parents=True, exist_ok=True)
    skill_text = f"---\nname: {folder.name}\n{_yaml_description(description_text)}\n---\n\n{body.strip()}\n"
    existing.write_text(skill_text, encoding="utf-8")
    written.append(existing)

    if script is not None:
        script.parent.mkdir(parents=True, exist_ok=True)
        script.write_text(script_code if script_code.endswith("\n") else script_code + "\n", encoding="utf-8")
        written.append(script)

    if notes is not None:
        notes.write_text(
            reference_markdown if reference_markdown.endswith("\n") else reference_markdown + "\n",
            encoding="utf-8",
        )
        written.append(notes)

    listing = "\n".join(_from_lab(path) for path in written)
    print(f"Saved skill: {folder.name}")
    return f"Saved skill {folder.name}.\n{folder}\n{listing}"


def list_skills() -> str:
    """List skill folders and the first line of each description."""
    names = skill_names()
    if not names:
        return "No skills yet."
    lines = []
    for name in names:
        description, _body = _split_skill((SKILLS_DIR / name / "SKILL.md").read_text(encoding="utf-8"))
        lines.append(f"{name}: {description or '(no description)'}")
    return "\n".join(lines)


def read_skill(name: str) -> str:
    """Read one skill's SKILL.md and the names of its other files.

    name: the skill folder name
    """
    folder = _skill_dir(name)
    if isinstance(folder, str):
        return folder
    skill_md = folder / "SKILL.md"
    if not skill_md.is_file():
        return f"No skill named {folder.name}."
    parts = [f"folder: {_from_lab(folder)}", "", skill_md.read_text(encoding="utf-8")[:12000]]
    extras = [
        str(path.relative_to(folder))
        for path in sorted(folder.rglob("*"))
        if path.is_file() and path.name != "SKILL.md" and not path.name.startswith(".")
    ]
    if extras:
        parts.extend(["", "other files: " + ", ".join(extras)])
    return "\n".join(parts)


def run_skill_script(skill: str, filename: str, extra_args: str = "") -> str:
    """Run a Python script from a skill's scripts folder. The working directory is the lab folder.

    skill: the skill folder name
    filename: the script file name, such as filter_ssid.py
    extra_args: arguments the skill tells you to pass
    """
    folder = _skill_dir(skill)
    if isinstance(folder, str):
        return folder
    if not (folder / "SKILL.md").is_file():
        return f"No skill named {folder.name}."
    script = _script_file(folder, filename)
    if isinstance(script, str):
        return script
    if not script.is_file():
        return f"No script {script.name} in {folder.name}."
    extra = shlex.split(extra_args) if extra_args.strip() else []
    before = _image_stamps()
    try:
        completed = subprocess.run(
            [sys.executable, str(script), *extra],
            capture_output=True,
            text=True,
            timeout=90,
            cwd=str(LAB),
            env={**os.environ},
        )
    except subprocess.TimeoutExpired:
        _keep_new_images(before)
        return "The script ran longer than 90 seconds and was stopped."
    _keep_new_images(before)
    out = (completed.stdout or "") + (completed.stderr or "")
    return f"exit_code={completed.returncode}\n{out[-4000:]}"


def remove_skill(name: str) -> str:
    """Delete one skill folder from Skills/.

    name: the skill folder name
    """
    folder = _skill_dir(name)
    if isinstance(folder, str):
        return folder
    if not (folder / "SKILL.md").is_file():
        return f"No skill named {folder.name}."
    shutil.rmtree(folder)
    return f"Removed skill {folder.name}."


save_skill_tool = function_tool(save_skill)
list_skills_tool = function_tool(list_skills)
read_skill_tool = function_tool(read_skill)
run_skill_script_tool = function_tool(run_skill_script)
remove_skill_tool = function_tool(remove_skill)


@function_tool
def list_agents() -> str:
    """List the agents and sub-agents in this chat."""
    return agent_tree()


@function_tool
def remove_agent(name: str) -> str:
    """Remove an agent and every sub-agent under it.

    name: the agent to remove
    """
    title = name.strip()
    agents = load_registry()
    if find_agent(agents, title) is None:
        return f"No agent named {title}."

    def drop_names(root: str) -> set[str]:
        gone = {root.strip().lower()}
        changed = True
        while changed:
            changed = False
            for record in agents:
                parent = str(record.get("parent", "")).strip().lower()
                agent_name = str(record.get("name", "")).strip().lower()
                if parent in gone and agent_name not in gone:
                    gone.add(agent_name)
                    changed = True
        return gone

    gone = drop_names(title)
    kept = [record for record in agents if str(record.get("name", "")).strip().lower() not in gone]
    save_registry(kept)
    removed = [str(record.get("name")) for record in agents if str(record.get("name", "")).strip().lower() in gone]
    return "Removed " + ", ".join(removed) + "."


def is_mcp_server(path: Path) -> bool:
    """True when a Codes file is launched as an MCP server."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    return "mcp.run(" in text


def mcp_server_files() -> list[Path]:
    if not CODES_DIR.is_dir():
        return []
    files = [path for path in CODES_DIR.glob("*.py") if is_mcp_server(path)]
    return sorted(files, key=lambda path: ("backup" in path.name.lower(), path.name.lower()))


async def _drop_mcp(path_key: str) -> None:
    item = _mcp_servers.pop(path_key, None)
    if item is None:
        return
    try:
        await item[1].cleanup()
    except Exception:
        pass


async def prepare_mcp_servers() -> tuple[list[MCPServerStdio], str]:
    """Start every MCP server in Codes/ and keep each process until that file changes."""
    wanted = {str(path.resolve()): path for path in mcp_server_files()}
    lines = ["MCP servers:"]
    connected: list[MCPServerStdio] = []
    seen_tools: set[str] = set()
    async with _mcp_lock:
        for key in list(_mcp_servers):
            if key not in wanted:
                await _drop_mcp(key)
        for key, path in wanted.items():
            stamp = path.stat().st_mtime_ns
            current = _mcp_servers.get(key)
            if current is not None and current[0] != stamp:
                await _drop_mcp(key)
                current = None
            if current is None:
                server = MCPServerStdio(
                    params={
                        "command": sys.executable,
                        "args": [str(path)],
                        "env": {**os.environ},
                        "cwd": str(LAB),
                    },
                    client_session_timeout_seconds=120,
                    cache_tools_list=True,
                    name=path.stem,
                )
                try:
                    await server.connect()
                except Exception as exc:
                    try:
                        await server.cleanup()
                    except Exception:
                        pass
                    lines.append(
                        f"- Codes/{path.name} did not connect: {type(exc).__name__}: {exc}. "
                        "Do not invent its data. Do not ask the student to run a command."
                    )
                    continue
                _mcp_servers[key] = (stamp, server)
                current = _mcp_servers[key]
            server = current[1]
            try:
                tools = await server.list_tools()
                names = sorted(tool.name for tool in tools)
            except Exception as exc:
                connected.append(server)
                lines.append(
                    f"- Codes/{path.name} is connected, but its tools could not be listed "
                    f"({type(exc).__name__}: {exc})."
                )
                continue
            overlap = sorted(set(names) & seen_tools)
            if overlap:
                await _drop_mcp(key)
                lines.append(
                    f"- Codes/{path.name} was not connected. "
                    f"These tools are already provided by another MCP server: {', '.join(overlap)}."
                )
                continue
            seen_tools.update(names)
            connected.append(server)
            shown = ", ".join(names) or "(no tools)"
            lines.append(
                f"- Codes/{path.name} is connected. Tools: {shown}. "
                "Call the matching tool. Do not run this file with run_saved_python."
            )
    if len(lines) == 1:
        return [], ""
    lines.append("- A server saved during this message is connected on the next message.")
    return connected, "\n".join(lines)


def make_model(backend: str, model_name: str):
    if backend == "ollama":
        return OpenAIChatCompletionsModel(model=model_name, openai_client=ollama_client)
    return model_name


def make_turn_agent(
    provider: str,
    model_name: str,
    mcp_servers: list | None = None,
    extra_instructions: str = "",
) -> tuple[str, str, Agent]:
    """Build the chat agent, with any agents the student has created as tools."""
    backend = backend_of(provider)
    provider_label = "Ollama" if backend == "ollama" else "OpenAI"
    fallback = OPENAI_MODELS[0] if provider_label == "OpenAI" else OLLAMA_MODEL
    name = (model_name or "").strip() or fallback
    model = make_model(backend, name)
    records = load_registry()
    used_slugs: set[str] = set()

    def tool_name_for(title: str) -> str:
        base = slug(title)
        candidate = base
        number = 2
        while candidate in used_slugs:
            candidate = f"{base}_{number}"
            number += 1
        used_slugs.add(candidate)
        return candidate

    def code_tools(record: dict) -> list:
        tools = [read_capture]
        if record.get("can_code"):
            tools.extend([list_workspace, save_python_code, run_saved_python])
        return tools

    pending: dict[str, Agent] = {}
    building: set[str] = set()

    def build_record(record: dict) -> Agent:
        key = str(record["name"]).strip().lower()
        if key in pending:
            return pending[key]
        if key in building:
            raise ValueError(f"Agent loop at {record['name']}")
        building.add(key)
        children = [
            other
            for other in records
            if str(other.get("parent", "")).strip().lower() == key
        ]
        child_tools = []
        for child in children:
            child_agent = build_record(child)
            child_tools.append(
                child_agent.as_tool(
                    tool_name=tool_name_for(str(child["name"])),
                    tool_description=str(child.get("instructions", ""))[:300],
                )
            )
        extra = ""
        if children:
            names = ", ".join(str(child["name"]) for child in children)
            extra = f"\n\nYou have these sub-agents as tools: {names}. Delegate the work that matches a sub-agent. Do not do that work yourself."
        body = str(record.get("instructions", "")).strip()
        if "read_capture" not in body:
            body += CAPTURE_RULE
        agent = Agent(
            name=str(record["name"]),
            instructions=body + extra,
            tools=[*code_tools(record), *child_tools],
            model=model,
            model_settings=ModelSettings(tool_choice="auto"),
        )
        pending[key] = agent
        building.discard(key)
        return agent

    top_level_tools = []
    for record in records:
        if str(record.get("parent", "")).strip():
            continue
        agent = build_record(record)
        top_level_tools.append(
            agent.as_tool(
                tool_name=tool_name_for(str(record["name"])),
                tool_description=str(record.get("instructions", ""))[:300],
            )
        )

    builder_tools = [
        list_workspace,
        read_capture,
        save_python_code,
        run_saved_python,
        create_agent,
        get_agent_tool,
        update_agent_tool,
        list_agents,
        remove_agent,
        save_skill_tool,
        list_skills_tool,
        read_skill_tool,
        run_skill_script_tool,
        remove_skill_tool,
    ]
    instructions = INSTRUCTIONS
    if extra_instructions.strip():
        instructions = f"{instructions}\n\n{extra_instructions.strip()}"
    builder = Agent(
        name="Lab Builder",
        instructions=instructions,
        tools=[*builder_tools, *top_level_tools],
        mcp_servers=list(mcp_servers or []),
        model=model,
        model_settings=ModelSettings(tool_choice="auto"),
    )
    return backend, name, builder


def store_upload(src: str) -> Path:
    """Copy a chat attachment into Uploads/ and return the saved path."""
    UPLOADS.mkdir(parents=True, exist_ok=True)
    source = Path(src)
    dest = UPLOADS / source.name
    if dest.exists():
        stem, suffix = dest.stem, dest.suffix
        n = 2
        while dest.exists():
            dest = UPLOADS / f"{stem}_{n}{suffix}"
            n += 1
    dest.write_bytes(source.read_bytes())
    return dest


def _read_text(path: Path) -> str | None:
    data = path.read_bytes()[: MAX_CHARS * 4]
    if b"\x00" in data[:1024]:
        return None
    text = data.decode("utf-8", errors="replace")
    if text.count("\ufffd") > 20:
        return None
    clipped = text[:MAX_CHARS]
    if len(text) > MAX_CHARS:
        clipped += "\n[truncated]"
    return clipped


def file_note(path: Path, backend: str) -> str:
    """Text the model is allowed to see about one saved file."""
    suffix = path.suffix.lower()
    size = path.stat().st_size if path.is_file() else 0
    if suffix in IMAGE_SUFFIXES:
        if backend == "openai" and size <= MAX_IMAGE_BYTES:
            return (
                f"[Image attached: {path.name}. This is a picture, not a capture. "
                "If the student says it is an example, match its style. "
                "The numbers come from a pcap in this conversation.]"
            )
        if backend == "ollama":
            return (
                f"[Image saved as {path.name}, {size} bytes. "
                "This Ollama model reads text only and cannot see the picture.]"
            )
        return f"[Image saved as {path.name}, {size} bytes. It is too large to attach.]"
    if suffix == ".pdf":
        try:
            reader = PdfReader(str(path))
            pages = []
            for page in reader.pages[:3]:
                pages.append(page.extract_text() or "")
            text = "\n".join(pages)[:MAX_CHARS]
        except Exception as exc:
            return f"[PDF {path.name} could not be read: {exc}]"
        if not text.strip():
            return f"[PDF {path.name} has no extractable text.]"
        return f"[PDF {path.name}]\n{text}"
    if suffix in CAPTURE_SUFFIXES:
        try:
            summary = cached_summary(path)
        except Exception as exc:
            return (
                f"[Capture {path.name} is saved in Uploads/ but could not be read: {exc}. "
                "Call read_capture. Do not ask the student to run a command.]"
            )
        return (
            f"[Capture {path.name} — already read from the file. "
            "Use this reading. Call read_capture for another pass or one MAC. "
            "Do not ask the student to run a command.]\n"
            f"{summary}"
        )
    if suffix in BINARY_SUFFIXES:
        return (
            f"[Binary file saved as {path.name}, {size} bytes. "
            "Contents are not in this message. Do not invent what is inside.]"
        )
    text = _read_text(path) if path.is_file() else None
    if text is None:
        return (
            f"[File saved as {path.name}, {size} bytes. "
            "Contents are not in this message. Do not invent what is inside.]"
        )
    return f"[File {path.name}]\n{text}"


def _part_path(part) -> str | None:
    if isinstance(part, dict):
        if part.get("path"):
            return str(part["path"])
        nested = part.get("file")
        if isinstance(nested, dict) and nested.get("path"):
            return str(nested["path"])
    return None


def _part_text(part) -> str:
    if isinstance(part, str):
        return part
    if isinstance(part, dict) and (part.get("type") == "text" or ("text" in part and "file" not in part)):
        return str(part.get("text") or "")
    return ""


def _parts_from_content(content) -> tuple[str, list[Path]]:
    """Split a chat message into typed text and file paths.

    Gradio sends a stored turn back as a list of {"type": "text"} and {"type": "file"} parts.
    """
    if content is None:
        return "", []
    if isinstance(content, str):
        return content.strip(), []
    texts: list[str] = []
    paths: list[Path] = []
    if isinstance(content, dict) and ("text" in content or "files" in content) and content.get("type") != "text":
        texts.append(str(content.get("text") or ""))
        for item in content.get("files") or []:
            raw = item if isinstance(item, str) else _part_path(item)
            if raw:
                paths.append(Path(raw))
        return "\n".join(t for t in texts if t.strip()).strip(), paths
    parts = content if isinstance(content, list) else [content]
    for part in parts:
        text = _part_text(part)
        if text.strip():
            texts.append(text)
            continue
        raw = _part_path(part) if isinstance(part, dict) else None
        if raw:
            paths.append(Path(raw))
    if texts or paths:
        return "\n".join(t for t in texts if t.strip()).strip(), paths
    return str(content).strip(), []


def _image_part(path: Path) -> dict | None:
    if path.suffix.lower() not in IMAGE_SUFFIXES or not path.is_file():
        return None
    if path.stat().st_size > MAX_IMAGE_BYTES:
        return None
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return {
        "type": "input_image",
        "image_url": f"data:{mime};base64,{encoded}",
        "detail": "auto",
    }


def message_item(role: str, content, backend: str) -> dict:
    text, paths = _parts_from_content(content)
    notes = [file_note(path, backend) for path in paths if path.is_file()]
    body = "\n\n".join(piece for piece in [text, *notes] if piece)
    images = []
    if backend == "openai":
        images = [part for path in paths if (part := _image_part(path))]
    if images:
        return {
            "role": role,
            "content": [{"type": "input_text", "text": body or "Attached files."}, *images],
        }
    return {"role": role, "content": body or "(empty message)"}


def display_user_message(text: str, paths: list[Path]) -> dict:
    content: list = [{"path": str(path)} for path in paths]
    content.append(text or "(file attached)")
    return {"role": "user", "content": content}


async def reply(history, provider: str, model_name: str) -> str:
    mcp_servers, mcp_note = await prepare_mcp_servers()
    backend, model_name, agent = make_turn_agent(
        provider,
        model_name,
        mcp_servers=mcp_servers,
        extra_instructions=mcp_note,
    )
    label = "Ollama" if backend == "ollama" else "OpenAI"
    items = [message_item(turn.get("role", "user"), turn.get("content"), backend) for turn in history or []]
    if not items:
        return "Type a message or attach a file."

    set_tracing_disabled(backend == "ollama")
    print(f"{label} → {backend} · {model_name} · turns={len(items)}")
    token = _NEW_IMAGES.set([])
    try:
        try:
            result = await Runner.run(agent, items)
            used = []
            for item in result.new_items:
                raw = getattr(item, "raw_item", None)
                tool_name = getattr(raw, "name", None)
                if tool_name:
                    used.append(tool_name)
            if used:
                print("Tools:", ", ".join(used))
            output = (result.final_output or "").strip() or "(The model returned no text.)"
        except Exception as exc:
            output = f"Error: {type(exc).__name__}: {exc}"
        images = list(_NEW_IMAGES.get() or [])
    finally:
        _NEW_IMAGES.reset(token)
    body = f"**{label}** · `{model_name}`\n\n{output}"
    if not images:
        return body
    return [body, *({"path": path} for path in images[:6])]


def build_demo() -> gr.Blocks:
    with gr.Blocks(title="Lab Builder", fill_height=True) as demo:
        with gr.Column(scale=0):
            gr.Markdown("Hi, I'm your AI Assistant 🤖")
            with gr.Row():
                provider = gr.Radio(
                    choices=PROVIDERS,
                    value="OpenAI",
                    label="LLM",
                    scale=1,
                )
                openai_model = gr.Dropdown(
                    choices=OPENAI_MODELS,
                    value=OPENAI_MODELS[0],
                    label="OpenAI model",
                    filterable=False,
                    scale=2,
                )
                ollama_model = gr.Textbox(
                    value=OLLAMA_MODEL,
                    label="Ollama model",
                    info="A model you have pulled, such as qwen2.5:7b.",
                    visible=False,
                    scale=2,
                )
                clear = gr.Button("Clear chat", scale=0)
        with gr.Row(scale=1, elem_id="chat-row"):
            chatbot = gr.Chatbot(
                scale=3,
                label="Chat",
                elem_id="chatbot",
                height="100%",
            )
            roster = gr.Textbox(
                value=agent_tree(),
                label="Agents and skills",
                lines=8,
                interactive=False,
                elem_id="agent-roster",
                scale=1,
            )
        box = gr.MultimodalTextbox(
            file_count="multiple",
            lines=1,
            max_lines=6,
            scale=0,
            elem_id="composer",
            placeholder="Ask it to build an agent, change one, or write a skill. Enter sends.",
            show_label=False,
            autofocus=True,
        )
        waiting = gr.State(False)

        def show_user_message(message, history):
            text, incoming = _parts_from_content(message)
            saved = [store_upload(str(path)) for path in incoming if path.is_file()]
            updated = list(history or [])
            if not text and not saved:
                return updated, {"text": "", "files": []}, False
            updated.append(display_user_message(text, saved))
            return updated, {"text": "", "files": []}, True

        async def on_submit(history, provider_name, openai_name, ollama_name, is_waiting):
            updated = list(history or [])
            if not is_waiting:
                return updated, agent_tree(), False
            model_name = openai_name if provider_name == "OpenAI" else ollama_name
            answer = await reply(updated, provider_name, model_name)
            updated.append({"role": "assistant", "content": answer})
            return updated, agent_tree(), False

        # Client-side only. A queued visibility update leaves Gradio's progress
        # overlay on the textbox, so the model name never appears.
        provider.change(
            None,
            inputs=provider,
            outputs=[openai_model, ollama_model],
            js="""(providerName) => {
                const openai = providerName === "OpenAI";
                return [
                    {__type__: "update", visible: openai},
                    {__type__: "update", visible: !openai},
                ];
            }""",
        )
        box.submit(
            show_user_message,
            [box, chatbot],
            [chatbot, box, waiting],
            show_progress="hidden",
        ).then(
            on_submit,
            [chatbot, provider, openai_model, ollama_model, waiting],
            [chatbot, roster, waiting],
        )
        clear.click(lambda: ([], False), outputs=[chatbot, waiting])
    return demo


CHAT_CSS = """
footer { display: none !important; }
.gradio-container {
  height: 100dvh !important;
  max-height: 100dvh !important;
  overflow: hidden !important;
}
.gradio-container .wrap,
.gradio-container main.contain {
  min-height: 0 !important;
  flex: 1 1 auto !important;
  overflow: hidden !important;
}
.gradio-container main.contain {
  display: flex !important;
  flex-direction: column !important;
}
.gradio-container main.contain > .column {
  min-height: 0 !important;
  height: 100% !important;
  overflow: hidden !important;
}
#chat-row {
  flex: 1 1 0 !important;
  min-height: 0 !important;
  overflow: hidden !important;
  align-items: stretch !important;
}
#chatbot {
  align-self: stretch !important;
  height: 100% !important;
  min-height: 0 !important;
  max-height: 100% !important;
  overflow: hidden !important;
}
#chatbot .wrapper {
  flex: 1 1 0 !important;
  min-height: 0 !important;
  height: auto !important;
  width: 100% !important;
  overflow: hidden !important;
  align-items: stretch !important;
}
#chatbot .bubble-wrap,
#chatbot .panel-wrap {
  flex: 1 1 0 !important;
  min-height: 0 !important;
  height: 100% !important;
  max-height: 100% !important;
  width: 100% !important;
  overflow-y: auto !important;
  overscroll-behavior: contain;
  overflow-anchor: none;
}
#chatbot pre, #chatbot code {
  white-space: pre-wrap !important;
  overflow: visible !important;
}
#agent-roster, #agent-roster textarea {
  height: 100% !important;
  min-height: 0 !important;
}
#agent-roster textarea { overflow: auto !important; }
#composer {
  flex: 0 0 auto !important;
}
#composer textarea {
  line-height: 1.45 !important;
  overflow-y: auto !important;
}
"""

CHAT_SCROLL_JS = """
<script>
(() => {
  const chatScroll = (node) => node instanceof Element
    && !!node.closest("#chatbot")
    && (node.classList.contains("bubble-wrap") || node.classList.contains("panel-wrap"));
  const nearBottom = (el) => el.scrollHeight - el.scrollTop - el.clientHeight < 48;
  document.addEventListener("scroll", (event) => {
    const wrap = event.target;
    if (!chatScroll(wrap)) return;
    wrap.dataset.hold = nearBottom(wrap) ? "0" : "1";
  }, true);
  const scrollTo = Element.prototype.scrollTo;
  Element.prototype.scrollTo = function (...args) {
    if (this.dataset && this.dataset.hold === "1" && chatScroll(this)) return;
    return scrollTo.apply(this, args);
  };
})();
</script>
"""


def main(inbrowser: bool = True, server_port: int | None = None) -> None:
    UPLOADS.mkdir(parents=True, exist_ok=True)
    CODES_DIR.mkdir(parents=True, exist_ok=True)
    build_demo().launch(
        inbrowser=inbrowser,
        server_port=server_port,
        css=CHAT_CSS,
        head=CHAT_SCROLL_JS,
    )


if __name__ == "__main__":
    main()
