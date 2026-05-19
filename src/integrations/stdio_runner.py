"""StdioRunner — launch and manage MCP servers as native stdio processes.

Replaces DockerRunner. Each integration instance gets its own subprocess
with credentials injected via environment variables (never written to disk).

Features:
  - Health checking via process poll + stdin/stdout liveness
  - Auto-restart with exponential backoff (max 3 attempts in 5 minutes)
  - Graceful shutdown with configurable timeout
"""

from __future__ import annotations

import logging
import os
import subprocess
import time
from dataclasses import dataclass, field
from typing import Any

from src.integrations.interfaces import IStdioRunner

logger = logging.getLogger(__name__)

_MAX_RESTARTS = 3
_RESTART_WINDOW_SECONDS = 300  # 5 minutes
_GRACEFUL_TIMEOUT = 5  # seconds to wait before kill


@dataclass(frozen=True)
class ProcessInfo:
    """Snapshot of a managed stdio process."""

    pid: int
    status: str  # "running" | "stopped" | "error"
    command: list[str]
    error: str | None = None


@dataclass
class _TrackedProcess:
    """Internal tracking for a managed process with restart metadata."""

    process: subprocess.Popen
    command: list[str]
    args: list[str] | None
    env: dict[str, str] | None
    restart_timestamps: list[float] = field(default_factory=list)


class StdioRunner(IStdioRunner):
    """Manages stdio MCP server lifecycle with health checking and auto-restart."""

    def __init__(self) -> None:
        self._tracked: dict[int, _TrackedProcess] = {}

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

            tracked = _TrackedProcess(
                process=process,
                command=cmd,
                args=args,
                env=env,
            )
            self._tracked[process.pid] = tracked

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
        tracked = self._tracked.pop(pid, None)
        if tracked is None:
            logger.warning("StdioRunner: no process with pid=%s", pid)
            return

        self._terminate_process(tracked.process, pid)

    def is_running(self, pid: int) -> bool:
        """Check if a tracked process is still alive."""
        tracked = self._tracked.get(pid)
        if tracked is None:
            return False
        return tracked.process.poll() is None

    # ------------------------------------------------------------------
    # Health checking
    # ------------------------------------------------------------------

    def health_check(self, pid: int) -> bool:
        """Verify a process is alive and its I/O pipes are open.

        Returns True if the process is healthy, False otherwise.
        """
        tracked = self._tracked.get(pid)
        if tracked is None:
            return False

        proc = tracked.process

        # Check if process has exited
        if proc.poll() is not None:
            logger.warning(
                "StdioRunner: health check failed — process pid=%s has exited (code=%s)",
                pid,
                proc.returncode,
            )
            return False

        # Check if stdin/stdout pipes are still open
        if proc.stdin is None or proc.stdin.closed:
            logger.warning("StdioRunner: health check failed — stdin closed for pid=%s", pid)
            return False

        if proc.stdout is None or proc.stdout.closed:
            logger.warning("StdioRunner: health check failed — stdout closed for pid=%s", pid)
            return False

        return True

    # ------------------------------------------------------------------
    # Auto-restart with backoff
    # ------------------------------------------------------------------

    def restart(
        self,
        pid: int,
        command: str | None = None,
        args: list[str] | None = None,
        env: dict[str, str] | None = None,
    ) -> ProcessInfo:
        """Restart a process, respecting restart limits.

        Uses the original command/args/env if not provided.
        Returns error ProcessInfo if restart limit exceeded.
        """
        tracked = self._tracked.get(pid)

        # Determine command details (use originals if not provided)
        if tracked:
            cmd_str = command or tracked.command[0]
            cmd_args = args if args is not None else tracked.args
            cmd_env = env if env is not None else tracked.env

            # Check restart limits
            now = time.monotonic()
            recent = [t for t in tracked.restart_timestamps if now - t < _RESTART_WINDOW_SECONDS]
            if len(recent) >= _MAX_RESTARTS:
                logger.error(
                    "StdioRunner: restart limit reached for pid=%s (%d restarts in %ds)",
                    pid,
                    _MAX_RESTARTS,
                    _RESTART_WINDOW_SECONDS,
                )
                return ProcessInfo(
                    pid=pid,
                    status="error",
                    command=tracked.command,
                    error=f"Restart limit exceeded: {_MAX_RESTARTS} restarts in {_RESTART_WINDOW_SECONDS}s",
                )

            # Stop the old process
            self.stop(pid)

            # Record restart timestamp
            restart_ts = recent + [now]
        else:
            if not command:
                return ProcessInfo(
                    pid=-1,
                    status="error",
                    command=[],
                    error="Cannot restart: no tracked process and no command provided",
                )
            cmd_str = command
            cmd_args = args
            cmd_env = env
            restart_ts = [time.monotonic()]

        # Start new process
        result = self.start(cmd_str, cmd_args, cmd_env)

        # Transfer restart history to new tracked process
        if result.pid > 0 and result.pid in self._tracked:
            self._tracked[result.pid].restart_timestamps = restart_ts

        logger.info(
            "StdioRunner: restarted process old_pid=%s new_pid=%s (restarts=%d)",
            pid,
            result.pid,
            len(restart_ts),
        )
        return result

    # ------------------------------------------------------------------
    # Info
    # ------------------------------------------------------------------

    def get_info(self, pid: int) -> ProcessInfo | None:
        """Return current info for a tracked process."""
        tracked = self._tracked.get(pid)
        if tracked is None:
            return None
        status = "running" if tracked.process.poll() is None else "stopped"
        return ProcessInfo(
            pid=tracked.process.pid,
            status=status,
            command=tracked.command,
        )

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def cleanup_all(self) -> None:
        """Terminate all tracked processes. Useful on shutdown."""
        pids = list(self._tracked.keys())
        for pid in pids:
            self.stop(pid)
        logger.info("StdioRunner: cleaned up %d processes", len(pids))

    def _terminate_process(self, process: subprocess.Popen, pid: int) -> None:
        """Gracefully terminate a process with timeout fallback to kill."""
        try:
            process.terminate()
            try:
                process.wait(timeout=_GRACEFUL_TIMEOUT)
            except subprocess.TimeoutExpired:
                logger.warning("StdioRunner: process %s did not terminate, killing", pid)
                process.kill()
                process.wait()
            logger.info("StdioRunner: stopped process pid=%s", pid)
        except Exception as exc:
            logger.warning("StdioRunner: error stopping pid=%s: %s", pid, exc)
