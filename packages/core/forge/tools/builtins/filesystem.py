from __future__ import annotations

from pathlib import Path

from forge.core.config import settings
from forge.core.logging import get_logger

logger = get_logger("forge.tools.builtins.filesystem")

_DEFAULT_BASE = settings.data_dir.resolve()
_current_workspace: str | None = None


def set_workspace(workspace: str | None) -> None:
    global _current_workspace
    _current_workspace = workspace


def _get_base() -> Path:
    if _current_workspace:
        p = Path(_current_workspace).resolve()
        p.mkdir(parents=True, exist_ok=True)
        return p
    return _DEFAULT_BASE


def _resolve_path(path_str: str) -> Path:
    base = _get_base()
    path = Path(path_str)
    if not path.is_absolute():
        path = base / path
    path = path.resolve()

    if not str(path).startswith(str(base)):
        raise PermissionError(
            f"Access denied: '{path}' is outside allowed directory '{base}'",
        )

    return path


def read_file(path: str) -> str:
    try:
        resolved = _resolve_path(path)
    except PermissionError as e:
        return f"Error: {e}"
    if not resolved.exists():
        return f"Error: file not found: {resolved}"
    if not resolved.is_file():
        return f"Error: not a file: {resolved}"

    try:
        content = resolved.read_text(encoding="utf-8")
        logger.info("read file", path=str(resolved), size=len(content))
        return content
    except Exception as e:
        return f"Error reading file: {e}"


def write_file(path: str, content: str) -> str:
    try:
        resolved = _resolve_path(path)
    except PermissionError as e:
        return f"Error: {e}"
    try:
        resolved.parent.mkdir(parents=True, exist_ok=True)
        resolved.write_text(content, encoding="utf-8")
        logger.info("wrote file", path=str(resolved), size=len(content))
        return f"File written: {resolved}"
    except Exception as e:
        return f"Error writing file: {e}"


def list_directory(path: str = "") -> str:
    try:
        resolved = _resolve_path(path) if path else _get_base()
    except PermissionError as e:
        return f"Error: {e}"
    if not resolved.exists():
        return f"Error: directory not found: {resolved}"
    if not resolved.is_dir():
        return f"Error: not a directory: {resolved}"

    try:
        entries = list(resolved.iterdir())
        lines = [f"Directory: {resolved}"]
        for entry in sorted(entries, key=lambda e: (not e.is_dir(), e.name.lower())):
            suffix = "/" if entry.is_dir() else ""
            lines.append(f"  {entry.name}{suffix}")
        return "\n".join(lines)
    except Exception as e:
        return f"Error listing directory: {e}"


def search_files(pattern: str, path: str = "") -> str:
    try:
        resolved = _resolve_path(path) if path else _get_base()
    except PermissionError as e:
        return f"Error: {e}"
    if not resolved.exists() or not resolved.is_dir():
        return f"Error: invalid directory: {resolved}"

    try:
        matches = list(resolved.rglob(pattern))
        if not matches:
            return f"No files matching '{pattern}' in {resolved}"

        base = _get_base()
        lines = [f"Found {len(matches)} file(s) matching '{pattern}':"]
        for match in sorted(matches)[:50]:
            rel = match.relative_to(base)
            lines.append(f"  {rel}")
        if len(matches) > 50:
            lines.append(f"  ... and {len(matches) - 50} more")
        return "\n".join(lines)
    except Exception as e:
        return f"Error searching files: {e}"
