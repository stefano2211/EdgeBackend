"""StdioRunner — launch and manage MCP servers as native stdio processes.

Replaces DockerRunner. Each integration instance gets its own subprocess
with credentials injected via environment variables (never written to disk).
"""

from __future__ import annotations

import logging
import os
import subprocess
from dataclasses import dataclass
from typing import Any

from src.integrations.interfaces import IStdioRunner

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProcessInfo:
    """Snapshot of a managed stdio process."""

    pid: int
    status: str  # "running" | "stopped" | "error"
    command: list[str]
    error: str | None = None


class StdioRunner(IStdioRunner):
    """Manages stdio MCP server lifecycle."""

    def __init__(self) -> None:
        # pid → Popen mapping for active processes
        self._processes: dict[int, subprocess.Popen] = {}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(
        self,
        command: str,
        args: list[str] | None,
        env: dict[str, str] | None,
    ) -> ProcessInfo:
        """Launch a stdio MCP server process.

        Args:
            command: Executable (e.g. "npx", "python", "uvx").
            args: Arguments list.
            env: Extra environment variables (credentials) merged into os.environ.

        Returns:
            ProcessInfo with the running process details.
        """
        cmd = [command] + (args or [])
        process_env = dict(os.environ)
        if env:
            process_env.update(env)

        logger.info("StdioRunner: starting %s", " ".join(cmd))

        try:
            process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=process_env,
                text=False,
            )
            self._processes[process.pid] = process

            logger.info(
                "StdioRunner: process started pid=%s command=%s",
                process.pid,
                cmd,
            )
            return ProcessInfo(
                pid=process.pid,
                status="running",
                command=cmd,
            )
        except Exception as exc:
            logger.exception("StdioRunner: failed to start process")
            return ProcessInfo(
                pid=-1,
                status="error",
                command=cmd,
                error=str(exc),
            )

    def stop(self, pid: int) -> None:
        """Gracefully terminate a process by PID."""
        process = self._processes.pop(pid, None)
        if process is None:
            logger.warning("StdioRunner: no process with pid=%s", pid)
            return

        try:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                logger.warning("StdioRunner: process %s did not terminate, killing", pid)
                process.kill()
                process.wait()
            logger.info("StdioRunner: stopped process pid=%s", pid)
        except Exception as exc:
            logger.warning("StdioRunner: error stopping pid=%s: %s", pid, exc)

    def is_running(self, pid: int) -> bool:
        """Check if a tracked process is still alive."""
        process = self._processes.get(pid)
        if process is None:
            return False
        return process.poll() is None

    def get_info(self, pid: int) -> ProcessInfo | None:
        """Return current info for a tracked process."""
        process = self._processes.get(pid)
        if process is None:
            return None
        status = "running" if process.poll() is None else "stopped"
        return ProcessInfo(
            pid=process.pid,
            status=status,
            command=process.args,  # type: ignore[arg-type]
        )

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def cleanup_all(self) -> None:
        """Terminate all tracked processes. Useful on shutdown."""
        pids = list(self._processes.keys())
        for pid in pids:
            self.stop(pid)
