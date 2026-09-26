"""
dev_control.py — JARVIS Dev: project loader and context provider (Step 1)

Responsibilities:
  - Set and remember an active project directory.
  - Walk it recursively to build a readable file tree.
  - Skip sensitive, binary, and oversized files.
  - Cache the result so every later feature can call get_project_context()
    without re-scanning the disk.
  - Persist the active project path in dev_config.json so it survives restarts.
"""

import os
import json
import pathlib

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

BASE_DIR = pathlib.Path(__file__).parent
CONFIG_PATH = BASE_DIR / "dev_config.json"

# Directories that are always skipped (matched against each directory name)
IGNORED_DIRS = {
    ".git", ".venv", "venv", "__pycache__", "node_modules",
    ".idea", ".vscode", ".mypy_cache", ".pytest_cache",
    "whatsapp_session", "jarvis_whatsapp_profile",
    "dist", "build", ".bob", ".tox",
}

# Individual file names that are always skipped
IGNORED_FILES = {
    "credentials.json", "token.json", "devlog.json",
    ".env", ".env.local", ".env.production",
    "id_rsa", "id_ed25519", "id_ecdsa",
}

# File extensions treated as binary — we list the tree entry but never read content
BINARY_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".webp", ".svg",
    ".mp3", ".mp4", ".wav", ".ogg", ".flac",
    ".zip", ".tar", ".gz", ".7z", ".rar",
    ".exe", ".dll", ".so", ".dylib", ".pyd",
    ".pdf", ".docx", ".xlsx", ".pptx",
    ".pyc", ".pyo",
    ".db", ".sqlite", ".sqlite3",
    ".bin", ".dat",
}

# Maximum characters read from any single text file (avoids huge files blowing the prompt)
MAX_FILE_CHARS = 8_000

# Maximum total characters of all file contents combined in the context snapshot
MAX_TOTAL_CHARS = 40_000

# ---------------------------------------------------------------------------
# Persistent config helpers
# ---------------------------------------------------------------------------

def _load_config() -> dict:
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _save_config(data: dict) -> None:
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


# ---------------------------------------------------------------------------
# In-memory cache (reset when set_active_project is called)
# ---------------------------------------------------------------------------

_active_project_path: str | None = None   # absolute path string
_file_tree: str = ""                       # human-readable tree (always available)
_file_contents: dict[str, str] = {}        # {relative_path: text_content}
_context_snapshot: str = ""               # combined string passed to prompts
_last_error: str = ""                      # most recently analysed error text (for follow-ups)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def set_active_project(path: str) -> str:
    """
    Point JARVIS Dev at a project directory.
    Walks the directory, builds the file tree and content cache, persists the
    path to dev_config.json, and returns a human-readable summary string.

    Returns a status string suitable for speaking or printing.
    """
    global _active_project_path, _file_tree, _file_contents, _context_snapshot, _last_error
    _last_error = ""   # clear cached error when switching projects

    project = pathlib.Path(path).resolve()
    if not project.exists():
        return f"Path does not exist: {path}"
    if not project.is_dir():
        return f"Not a directory: {path}"

    _active_project_path = str(project)
    _file_tree, _file_contents = _build_tree_and_contents(project)
    _context_snapshot = _build_context_snapshot(project.name, _file_tree, _file_contents)

    # persist so the path survives a restart
    cfg = _load_config()
    cfg["active_project"] = _active_project_path
    _save_config(cfg)

    file_count = len(_file_contents)
    tree_lines = _file_tree.count("\n") + 1
    return (
        f"Project '{project.name}' loaded. "
        f"{tree_lines} files/dirs in tree, {file_count} text files indexed."
    )


def get_active_project_path() -> str | None:
    """Returns the absolute path of the currently loaded project, or None."""
    return _active_project_path


def get_file_tree() -> str:
    """Returns the plain-text file tree string (empty string if no project loaded)."""
    return _file_tree


def get_file_contents() -> dict[str, str]:
    """Returns the dict of {relative_path: content} for all readable text files."""
    return _file_contents


def get_project_context() -> str:
    """
    Returns the full context snapshot string — file tree + sampled file contents —
    ready to be injected into an Ollama prompt.
    Returns an empty string if no project has been loaded yet.
    """
    return _context_snapshot


def get_file_content(relative_path: str) -> str | None:
    """
    Retrieve the cached content of a single file by its relative path.
    Returns None if the file is not in the index (binary, too large, ignored, etc.).
    """
    return _file_contents.get(relative_path)


def restore_last_project() -> str:
    """
    Called at startup: re-loads the last active project from dev_config.json.
    Returns a status string (empty string if nothing was saved).
    """
    cfg = _load_config()
    last = cfg.get("active_project", "")
    if last:
        return set_active_project(last)
    return ""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _should_skip_dir(dir_name: str) -> bool:
    return dir_name in IGNORED_DIRS or dir_name.startswith(".")


def _should_skip_file(file_name: str) -> bool:
    return file_name in IGNORED_FILES or file_name.startswith(".")


def _is_binary(file_path: pathlib.Path) -> bool:
    return file_path.suffix.lower() in BINARY_EXTENSIONS


def _build_tree_and_contents(
    root: pathlib.Path,
) -> tuple[str, dict[str, str]]:
    """
    Recursively walks `root`, building:
      - a readable indented tree string  (every entry, binary or not)
      - a dict of relative_path → text content  (text files only, up to MAX_FILE_CHARS each)
    """
    tree_lines: list[str] = [f"{root.name}/"]
    contents: dict[str, str] = {}

    def _walk(directory: pathlib.Path, prefix: str) -> None:
        try:
            entries = sorted(directory.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
        except PermissionError:
            return

        dirs   = [e for e in entries if e.is_dir()  and not _should_skip_dir(e.name)]
        files  = [e for e in entries if e.is_file() and not _should_skip_file(e.name)]

        all_visible = dirs + files
        for idx, entry in enumerate(all_visible):
            is_last = idx == len(all_visible) - 1
            connector = "└── " if is_last else "├── "
            child_prefix = prefix + ("    " if is_last else "│   ")

            if entry.is_dir():
                tree_lines.append(f"{prefix}{connector}{entry.name}/")
                _walk(entry, child_prefix)
            else:
                rel = str(entry.relative_to(root))
                if _is_binary(entry):
                    tree_lines.append(f"{prefix}{connector}{entry.name}  [binary]")
                else:
                    tree_lines.append(f"{prefix}{connector}{entry.name}")
                    _try_read_file(entry, rel, contents)

    _walk(root, "")
    return "\n".join(tree_lines), contents


def _try_read_file(file_path: pathlib.Path, rel: str, contents: dict[str, str]) -> None:
    """
    Attempts to read a text file. Skips it silently if it can't be decoded,
    is empty, or is over the per-file character limit.
    """
    try:
        size = file_path.stat().st_size
        if size == 0:
            return
        # rough guard: 4 bytes/char worst case; skip anything clearly too large
        if size > MAX_FILE_CHARS * 4:
            contents[rel] = f"[file too large to index: {size} bytes]"
            return
        text = file_path.read_text(encoding="utf-8", errors="strict")
        if len(text) > MAX_FILE_CHARS:
            text = text[:MAX_FILE_CHARS] + f"\n... [truncated at {MAX_FILE_CHARS} chars]"
        contents[rel] = text
    except (UnicodeDecodeError, PermissionError, OSError):
        # not a readable text file — silently skip
        pass


def analyze_project() -> str:
    """
    Uses the cached project context to ask Ollama for a structured overview of
    the active project. Covers: purpose, entry point, important files, modules,
    component connections, and potential problem areas.

    Returns a plain string suitable for speaking or printing.
    """
    if not _active_project_path:
        return "No project loaded. Say 'set project' followed by the path to load one."

    project_name = pathlib.Path(_active_project_path).name

    prompt = f"""You are a software engineer giving a brief verbal project briefing.
Your answer will be read aloud, so keep it SHORT — under 120 words total.

Summarise in this order:
1. One sentence: what the project does.
2. One sentence: main entry point and how it starts.
3. Two to four sentences: the most important files and what each does.
4. One sentence: any obvious risk or area for improvement (skip if none).

Rules:
- Only mention files and functions that exist in the project below.
- Do NOT list every file — pick the 3-5 most important ones.
- Do NOT include setup instructions, dependencies, or README-style content.
- Do NOT pad the answer. Be direct and concise.

{_context_snapshot}
"""

    try:
        import requests as _requests
        response = _requests.post(
            "http://localhost:11434/api/generate",
            json={"model": _get_config_model(), "prompt": prompt, "stream": False},
            timeout=None,  # local Ollama — wait as long as needed
        )
        data = response.json()
        return data.get("response", "").strip()
    except Exception as e:
        print("analyze_project error:", e)
        return "Sorry, I couldn't reach the AI model right now."


def _get_config_model() -> str:
    """Returns the model name from dev_config.json, defaulting to llama3.1:8b."""
    cfg = _load_config()
    return cfg.get("model", "llama3.1:8b")


def _resolve_filename(raw: str) -> "tuple[str, str] | tuple[None, None]":
    """
    Finds a file in _file_contents by matching the user's spoken filename against
    the indexed relative paths. Tries exact match first, then suffix match, then
    a loose stem match (strips extension and underscores for fuzzy spoken names).

    Returns (relative_path, content) if found, or (None, None) if not found.
    This is the hallucination guard — callers must check for None before prompting.
    """
    if not _file_contents:
        return None, None

    raw_clean = raw.strip().lower()

    # 1) exact match (case-insensitive)
    for rel, content in _file_contents.items():
        if rel.lower() == raw_clean:
            return rel, content

    # 2) suffix match — user says "vision_control.py", stored as "vision_control.py"
    for rel, content in _file_contents.items():
        if rel.lower().endswith(raw_clean):
            return rel, content

    # 3) stem match — user says "jarvis" or "vision control" (spoken without extension)
    raw_stem = raw_clean.replace(" ", "_").replace(".py", "").replace(".", "_")
    for rel, content in _file_contents.items():
        rel_stem = pathlib.Path(rel).stem.lower()
        if rel_stem == raw_stem:
            return rel, content

    # 4) partial stem match — user says "vision" → matches "vision_control.py"
    for rel, content in _file_contents.items():
        rel_stem = pathlib.Path(rel).stem.lower()
        if raw_stem in rel_stem or rel_stem in raw_stem:
            return rel, content

    return None, None


def ask_about_code(question: str) -> str:
    """
    Answers a free-form developer question grounded strictly in the indexed
    project files. Will not invent file names, functions, or behaviour not
    visible in the provided context.

    Returns a plain string suitable for speaking or printing.
    """
    if not _active_project_path:
        return "No project loaded. Say 'set project' followed by the path to load one."

    prompt = f"""You are a software engineer answering a question about a codebase. Answer will be read aloud.
Keep your answer SHORT: 2-4 sentences maximum.

Rules:
- Only refer to files, functions, and code visible in the project context below.
- If you cannot find the answer in the code, say so — do not guess or invent.
- Do NOT summarise the whole project. Answer only the specific question asked.
- Do NOT include setup instructions or feature lists.

Project context:
{_context_snapshot}

Question: {question}
"""

    try:
        import requests as _requests
        response = _requests.post(
            "http://localhost:11434/api/generate",
            json={"model": _get_config_model(), "prompt": prompt, "stream": False},
            timeout=None,  # local Ollama — wait as long as needed
        )
        data = response.json()
        return data.get("response", "").strip()
    except Exception as e:
        print("ask_about_code error:", e)
        return "Sorry, I couldn't reach the AI model right now."


def review_code(filename: str = "") -> str:
    """
    Reviews a specific file (or the full project if filename is empty) for bugs
    and improvements. Only ever refers to code actually present in the index.

    Returns a plain string suitable for speaking or printing.
    """
    if not _active_project_path:
        return "No project loaded. Say 'set project' followed by the path to load one."

    if filename:
        rel, content = _resolve_filename(filename)
        if rel is None:
            indexed = ", ".join(_file_contents.keys()) or "none"
            return (
                f"I couldn't find '{filename}' in the project index. "
                f"Indexed files are: {indexed}."
            )
        code_block = f"### {rel}\n```\n{content}\n```"
        scope_desc = f"the file '{rel}'"
    else:
        # full-project review using the complete snapshot
        code_block = _context_snapshot
        scope_desc = "the entire project"

    prompt = f"""You are a senior software engineer performing a code review of {scope_desc}.
Review the code below and identify:
- Confirmed bugs: logic errors, crashes, race conditions, or incorrect behaviour clearly visible in the code.
- Possible concerns: areas that could break under edge cases, style issues, or robustness improvements.
- Practical suggestions: concrete, specific changes that would improve the code.

IMPORTANT rules:
- Only refer to files, functions, variables, and code that appear in the provided code below.
- Clearly label each finding as either "Confirmed bug" or "Possible concern".
- Do not invent file names or functions that are not in the provided code.
- If the code looks clean, say so rather than fabricating issues.
- Write in plain prose so the answer can be read aloud. Keep the total response under 350 words.

{code_block}
"""

    try:
        import requests as _requests
        response = _requests.post(
            "http://localhost:11434/api/generate",
            json={"model": _get_config_model(), "prompt": prompt, "stream": False},
            timeout=None,  # local Ollama — wait as long as needed
        )
        data = response.json()
        return data.get("response", "").strip()
    except Exception as e:
        print("review_code error:", e)
        return "Sorry, I couldn't reach the AI model right now."


def explain_error(error_text: str) -> str:
    """
    Analyses a runtime error message or stack trace.
    Cross-references filenames found in the error against the indexed project
    files to supply relevant source context to the model.

    Returns a structured plain-text analysis suitable for speaking or printing.
    Never modifies any project files.
    """
    global _last_error

    if not error_text or not error_text.strip():
        return "No error text provided. Please supply an error message or stack trace."

    _last_error = error_text.strip()

    # --- cross-reference filenames from the error against the project index ---
    import re as _re
    mentioned_files = _re.findall(r'[\w/\\]+\.py', error_text)
    relevant_sources: list[str] = []
    for raw in dict.fromkeys(mentioned_files):          # deduplicate, preserve order
        rel, content = _resolve_filename(raw)
        if rel is not None:
            relevant_sources.append(f"### {rel} (referenced in error)\n```\n{content}\n```")

    sources_block = "\n\n".join(relevant_sources) if relevant_sources else ""
    context_note = (
        f"Active project file tree:\n{_file_tree}\n\n{sources_block}"
        if _active_project_path
        else "No active project loaded — analysing error without project context."
    )

    prompt = f"""You are a software engineer analyzing a runtime error. Your response will be read aloud.

YOUR ONLY JOB IS TO ANALYZE THIS SPECIFIC ERROR:
{error_text}

Respond using EXACTLY this format (each on its own line, no extra prose):
Error: [error type/class]
Cause: [most likely cause, 1 sentence]
Relevant code: [file and function only if confirmed in the project context below — otherwise write "Cannot confirm"]
Fix: [one concrete action to fix it]
Caveat: [only if there is a genuine uncertainty — otherwise omit this line entirely]

STRICT RULES:
- Do NOT describe the project, its features, or its architecture.
- Do NOT mention files or functions that are not in the error text or the project context below.
- Do NOT invent a cause if the error text is ambiguous — write "Cannot determine from available context" for Cause.
- Your entire response must be under 80 words.
- Output ONLY the formatted fields above. Nothing else.

Project context (for cross-referencing only):
{context_note}
"""

    try:
        import requests as _requests
        response = _requests.post(
            "http://localhost:11434/api/generate",
            json={"model": _get_config_model(), "prompt": prompt, "stream": False},
            timeout=None,  # local Ollama — wait as long as needed
        )
        data = response.json()
        return data.get("response", "").strip()
    except Exception as e:
        print("explain_error error:", e)
        return "Sorry, I couldn't reach the AI model right now."


def detect_project_errors() -> str:
    """
    Statically analyses the full indexed project for potential bugs and
    problematic logic — no user-supplied error needed.

    Every finding is strictly classified as one of:
      - Confirmed issue   (clear logic error visible in the code)
      - Possible concern  (risky pattern, edge case, style issue)
      - Cannot determine  (requires runtime info or testing to confirm)

    Never modifies any project files. Read-only.
    """
    if not _active_project_path:
        return "No project loaded. Say 'set project' followed by the path to load one."

    prompt = f"""You are a software engineer doing a static error scan. Response will be read aloud.

Scan the project source code below for bugs and problems. Report ONLY actual findings.

For each finding use this format:
[Confirmed issue | Possible concern] — [file/function if verified] — [what is wrong] — [short fix]

If you find nothing significant, respond with exactly:
No errors found, sir.

STRICT RULES:
- Do NOT describe the project, its purpose, its features, or its architecture.
- Do NOT mention setup, dependencies, or technology stack.
- Only mention files and functions that actually exist in the code below.
- Do not claim something is a "Confirmed issue" unless it is unambiguously wrong in the code.
- Keep the entire response under 150 words.
- If findings are minor, prefer "Possible concern" over "Confirmed issue".

{_context_snapshot}
"""

    try:
        import requests as _requests
        response = _requests.post(
            "http://localhost:11434/api/generate",
            json={"model": _get_config_model(), "prompt": prompt, "stream": False},
            timeout=None,  # local Ollama — wait as long as needed
        )
        data = response.json()
        return data.get("response", "").strip()
    except Exception as e:
        print("detect_project_errors error:", e)
        return "Sorry, I couldn't reach the AI model right now."


def generate_tests(filename: str = "") -> str:
    """
    Generates pytest-style unit tests for a specific file, or for the most
    testable functions across the whole project if no filename is given.

    Never modifies, creates, or overwrites any files — read-only.
    Never sends fabricated code to Ollama: the hallucination guard ensures
    only real indexed files reach the model.

    Returns the generated test code as a plain string.
    """
    if not _active_project_path:
        return "No project loaded. Say 'set project' followed by the path to load one."

    if filename:
        rel, content = _resolve_filename(filename)
        if rel is None:
            indexed = ", ".join(_file_contents.keys()) or "none"
            return (
                f"I couldn't find '{filename}' in the project index. "
                f"Indexed files are: {indexed}."
            )
        code_block = f"### {rel}\n```python\n{content}\n```"
        scope_desc = f"the file '{rel}'"
        test_file_hint = f"test_{rel}"
    else:
        code_block = _context_snapshot
        scope_desc = "the most important testable functions in the project"
        test_file_hint = "test_project.py"

    prompt = f"""You are a Python engineer. Generate pytest tests for {scope_desc}.

OUTPUT ONLY PYTHON CODE. No prose, no explanations outside of code comments.

Rules:
- First line must be a comment: # {test_file_hint}
- Only write tests for functions/classes that exist in the source code below.
- Do not import or reference anything not present in the source code.
- Use plain pytest functions (def test_...).
- Write at most 2 tests per function: one happy-path, one edge-case.
- Keep the entire output under 60 lines.
- Do NOT describe the project. Do NOT explain what you are doing. Just output the test code.

Source code:
{code_block}
"""

    try:
        import requests as _requests
        response = _requests.post(
            "http://localhost:11434/api/generate",
            json={"model": _get_config_model(), "prompt": prompt, "stream": False},
            timeout=None,  # local Ollama — wait as long as needed
        )
        data = response.json()
        return data.get("response", "").strip()
    except Exception as e:
        print("generate_tests error:", e)
        return "Sorry, I couldn't reach the AI model right now."


def _build_context_snapshot(
    project_name: str,
    tree: str,
    contents: dict[str, str],
) -> str:
    """
    Combines the file tree and file contents into a single string for prompt injection.
    Respects MAX_TOTAL_CHARS so the prompt doesn't explode on large projects.
    """
    header = f"=== Project: {project_name} ===\n\n"
    tree_block = f"--- File Tree ---\n{tree}\n\n"

    files_block_parts: list[str] = ["--- File Contents ---\n"]
    total = len(header) + len(tree_block)

    for rel, content in contents.items():
        if content.startswith("["):
            # placeholder messages (too large, etc.) — include them briefly
            entry = f"[{rel}]: {content}\n\n"
        else:
            entry = f"### {rel}\n```\n{content}\n```\n\n"

        if total + len(entry) > MAX_TOTAL_CHARS:
            files_block_parts.append(
                f"[...remaining files omitted — total context limit reached]\n"
            )
            break
        files_block_parts.append(entry)
        total += len(entry)

    return header + tree_block + "".join(files_block_parts)
