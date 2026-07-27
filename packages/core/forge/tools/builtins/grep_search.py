from __future__ import annotations

import re
from pathlib import Path

from forge.tools.builtins.filesystem import _get_base, _resolve_path
from forge.core.logging import get_logger

logger = get_logger("forge.tools.builtins.grep_search")


def grep_search(pattern: str, path: str = "", include: str = "*", max_results: int = 50) -> str:
    try:
        resolved = _resolve_path(path) if path else _get_base()
    except PermissionError as e:
        return f"Error: {e}"

    if not resolved.exists() or not resolved.is_dir():
        return f"Error: invalid directory: {resolved}"

    try:
        regex = re.compile(pattern)
    except re.error as e:
        return f"Error: invalid regex pattern '{pattern}': {e}"

    try:
        matches: list[tuple[Path, int, str]] = []
        import fnmatch

        for filepath in resolved.rglob("*"):
            if not filepath.is_file():
                continue
            if include != "*" and not fnmatch.fnmatch(filepath.name, include):
                continue

            try:
                content = filepath.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue

            for i, line in enumerate(content.splitlines(), 1):
                if regex.search(line):
                    matches.append((filepath, i, line.strip()))
                    if len(matches) >= max_results:
                        break
            if len(matches) >= max_results:
                break

        if not matches:
            return f"No matches found for '{pattern}' in {resolved}"

        base = _get_base()
        lines = [f"Found {len(matches)} match(es) for '{pattern}':"]
        for filepath, lineno, line in matches:
            rel = filepath.relative_to(base)
            lines.append(f"  {rel}:{lineno}: {line[:200]}")

        return "\n".join(lines)
    except Exception as e:
        return f"Error searching file contents: {e}"
