"""Shared conformance validator for live and offline tool-loop-v1 frames."""
from __future__ import annotations

import json
from typing import Any

PROTOCOL = "tool-loop-v1"
MAX_TURNS = 32
MAX_FRAME_BYTES = 65536


class ToolLoopProtocolError(ValueError):
    """Malformed, oversized, or out-of-order tool-loop protocol frame."""


class ProtocolValidator:
    """Validate the common agent-frame contract independent of transport.

    Live sessions require the protocol marker and supply the physical JSONL frame
    size. Offline replay accepts legacy event dictionaries without the marker,
    but rejects a marker when it is present and incorrect.
    """

    def __init__(self, *, require_protocol: bool = False,
                 max_turns: int = MAX_TURNS,
                 max_frame_bytes: int = MAX_FRAME_BYTES) -> None:
        if type(max_turns) is not int or max_turns < 1:
            raise ValueError("max_turns must be a positive integer")
        if type(max_frame_bytes) is not int or max_frame_bytes < 1:
            raise ValueError("max_frame_bytes must be a positive integer")
        self.require_protocol = require_protocol
        self.max_turns = max_turns
        self.max_frame_bytes = max_frame_bytes
        self.expected_turn = 1
        self.call_ids: set[str] = set()
        self.final_commit: dict[str, Any] | None = None

    @property
    def turns(self) -> int:
        return self.expected_turn - 1

    def accept(self, frame: Any, *, frame_size: int | None = None,
               require_protocol: bool | None = None) -> str:
        """Validate one decoded agent frame and return its event name."""
        if not isinstance(frame, dict):
            raise ToolLoopProtocolError("each agent frame must be an object")
        required = self.require_protocol if require_protocol is None else require_protocol
        marker = frame.get("protocol")
        if (required and marker != PROTOCOL) or (marker is not None and marker != PROTOCOL):
            raise ToolLoopProtocolError("invalid protocol frame")
        if frame_size is not None:
            if type(frame_size) is not int or frame_size < 0:
                raise ToolLoopProtocolError("frame size must be a non-negative integer")
            if frame_size > self.max_frame_bytes:
                raise ToolLoopProtocolError("protocol frame exceeds maximum size")
        else:
            try:
                encoded = json.dumps(
                    frame, ensure_ascii=False, separators=(",", ":")
                ).encode("utf-8")
            except (TypeError, ValueError, UnicodeError) as exc:
                raise ToolLoopProtocolError("frame is not JSON-serializable") from exc
            if len(encoded) > self.max_frame_bytes:
                raise ToolLoopProtocolError("protocol frame exceeds maximum size")
        if self.final_commit is not None:
            raise ToolLoopProtocolError("no frames may follow FINAL_COMMIT")
        turn = frame.get("turn_index")
        if type(turn) is not int or turn != self.expected_turn:
            raise ToolLoopProtocolError(f"turn_index must be integer {self.expected_turn}")
        if self.expected_turn > self.max_turns:
            raise ToolLoopProtocolError(f"turn limit exceeded ({self.max_turns})")
        event = frame.get("event")
        if event == "TOOL_CALL":
            call_id = frame.get("call_id")
            tool = frame.get("tool")
            if not isinstance(call_id, str) or not call_id or call_id in self.call_ids:
                raise ToolLoopProtocolError("call_id must be unique and non-empty")
            if not isinstance(tool, str) or not tool:
                raise ToolLoopProtocolError("tool must be a non-empty string")
            self.call_ids.add(call_id)
        elif event == "FINAL_COMMIT":
            payload = frame.get("payload")
            if not isinstance(payload, dict):
                raise ToolLoopProtocolError("FINAL_COMMIT payload must be an object")
            self.final_commit = payload
        else:
            raise ToolLoopProtocolError(f"unsupported event: {event!r}")
        self.expected_turn += 1
        return event
