"""ApparatusClaudeCode — a Harbor agent for RedlineBench.

Subclasses Harbor's stock `claude-code` agent and adds, purely on the
agent side (tasks, rubrics, and judges stay byte-identical):

  1. The Apparatus protocol as an appended system prompt (playbook rule
     cards -> written triage + dispositions -> surgical drafting ->
     mandatory deterministic gate).
  2. A pre-run environment setup that snapshots the pristine contract to
     /app/.apparatus/original.docx (so the gate can tell the agent's
     edits from the counterparty's) and installs the gate script plus a
     vendored copy of the benchmark's own docx_metrics.py.

Run through Harbor with:

    harbor run -p <tasks> -a redline_apparatus.agent:ApparatusClaudeCode \
        -m anthropic/claude-sonnet-5 ...
"""

from __future__ import annotations

import shlex
from pathlib import Path

from harbor.agents.installed.claude_code import ClaudeCode

from redline_apparatus.protocol import APPARATUS_PROTOCOL

_PAYLOAD_DIR = Path(__file__).resolve().parent / "payload"
_APPARATUS_DIR = "/app/.apparatus"


class ApparatusClaudeCode(ClaudeCode):
    """claude-code + the Apparatus grounding/verification overlay."""

    @classmethod
    def name(cls) -> str:
        return "apparatus-claude-code"

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("append_system_prompt", APPARATUS_PROTOCOL)
        super().__init__(*args, **kwargs)

    def build_cli_flags(self) -> str:
        """Like the base implementation, but shell-quotes values — the
        stock renderer interpolates flag values into a bash command
        unquoted, which breaks on any multi-line value (like our
        appended system prompt)."""
        parts: list[str] = []
        for flag in self.CLI_FLAGS:
            value = self._resolved_flags.get(flag.kwarg)
            if value is None:
                continue
            if flag.format is not None:
                parts.append(flag.format.format(value=shlex.quote(str(value))))
            elif flag.type == "bool":
                if value:
                    parts.append(flag.cli)
            else:
                parts.append(f"{flag.cli} {shlex.quote(str(value))}")
        return " ".join(parts)

    async def setup(self, environment) -> None:
        await super().setup(environment)

        # Snapshot the pristine contract before the agent ever runs, and
        # stage the gate + vendored benchmark metric module.
        await self.exec_as_root(
            environment,
            command=(
                f"mkdir -p {_APPARATUS_DIR} && "
                f"cp /app/contract.docx {_APPARATUS_DIR}/original.docx"
            ),
        )
        for fname, target in (
            ("apparatus_gate.py", f"{_APPARATUS_DIR}/gate.py"),
            ("docx_metrics.py", f"{_APPARATUS_DIR}/docx_metrics.py"),
        ):
            src = _PAYLOAD_DIR / fname
            if src.exists():
                await self._upload_agent_owned_file(environment, src, target)

        # The agent user must be able to write triage.json etc. in there.
        if environment.default_user is not None:
            user = shlex.quote(str(environment.default_user))
            await self.exec_as_root(
                environment,
                command=f"chown -R {user} {shlex.quote(_APPARATUS_DIR)}",
            )
