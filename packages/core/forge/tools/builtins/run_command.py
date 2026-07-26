from __future__ import annotations

import asyncio
from pathlib import Path

from forge.core.config import settings
from forge.core.logging import get_logger
from forge.tools.builtins.filesystem import _get_base, set_workspace

logger = get_logger("forge.tools.builtins.run_command")

_ALLOWED_BASE = settings.data_dir.resolve()


async def run_command(command: str, timeout: int = 30) -> str:
    if not command or not command.strip():
        return "Error: command cannot be empty"

    cwd = str(_get_base())
    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return f"Error: command timed out after {timeout}s"

        output = ""
        if stdout:
            output += stdout.decode("utf-8", errors="replace")
        if stderr:
            if output:
                output += "\n"
            output += stderr.decode("utf-8", errors="replace")

        logger.info(
            "ran command",
            command=command,
            returncode=proc.returncode,
            output_len=len(output),
        )
        return output.strip() or f"(command completed with exit code {proc.returncode})"

    except Exception as e:
        return f"Error executing command: {e}"
