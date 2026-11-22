import pytest

from gauntlet.protocol import (
    MAX_FRAME_BYTES,
    PROTOCOL,
    ProtocolValidator,
    ToolLoopProtocolError,
)
from gauntlet.tool_loop import evaluate_trace


def tool_call(turn=1, call_id="call-1"):
    return {
        "protocol": PROTOCOL,
        "event": "TOOL_CALL",
        "turn_index": turn,
        "call_id": call_id,
        "tool": "lookup_evidence",
        "arguments": {"evidence_id": "E1"},
    }


def final_commit(turn=1):
    return {
        "protocol": PROTOCOL,
        "event": "FINAL_COMMIT",
        "turn_index": turn,
        "payload": {"answer": "complete"},
    }


def test_live_validator_requires_protocol_marker():
    validator = ProtocolValidator(require_protocol=True)
    with pytest.raises(ToolLoopProtocolError, match="protocol"):
        validator.accept({"event": "FINAL_COMMIT", "turn_index": 1, "payload": {}})


def test_offline_validator_preserves_legacy_trace_compatibility():
    validator = ProtocolValidator()
    assert validator.accept({"event": "FINAL_COMMIT", "turn_index": 1, "payload": {}}) == "FINAL_COMMIT"


def test_wrong_protocol_marker_is_rejected_in_every_mode():
    validator = ProtocolValidator()
    frame = final_commit()
    frame["protocol"] = "tool-loop-v0"
    with pytest.raises(ToolLoopProtocolError, match="protocol"):
        validator.accept(frame)


def test_boolean_turn_index_is_not_an_integer():
    with pytest.raises(ToolLoopProtocolError, match="turn_index"):
        ProtocolValidator().accept(final_commit(True))


def test_turn_index_must_be_sequential():
    validator = ProtocolValidator()
    with pytest.raises(ToolLoopProtocolError, match="turn_index"):
        validator.accept(tool_call(turn=2))


def test_duplicate_call_ids_are_rejected():
    validator = ProtocolValidator()
    validator.accept(tool_call())
    with pytest.raises(ToolLoopProtocolError, match="unique"):
        validator.accept(tool_call(turn=2))


def test_final_commit_is_terminal():
    validator = ProtocolValidator()
    validator.accept(final_commit())
    with pytest.raises(ToolLoopProtocolError, match="follow"):
        validator.accept(tool_call(turn=2))


def test_final_commit_requires_object_payload():
    frame = final_commit()
    frame["payload"] = []
    with pytest.raises(ToolLoopProtocolError, match="payload"):
        ProtocolValidator().accept(frame)


def test_frame_size_limit_is_enforced_for_transport_and_replay():
    validator = ProtocolValidator(max_frame_bytes=MAX_FRAME_BYTES)
    with pytest.raises(ToolLoopProtocolError, match="maximum size"):
        validator.accept(final_commit(), frame_size=MAX_FRAME_BYTES + 1)

    oversized = final_commit()
    oversized["padding"] = "x" * MAX_FRAME_BYTES
    with pytest.raises(ToolLoopProtocolError, match="maximum size"):
        ProtocolValidator().accept(oversized)


def test_turn_limit_is_enforced():
    validator = ProtocolValidator(max_turns=1)
    validator.accept(tool_call())
    with pytest.raises(ToolLoopProtocolError, match="turn limit"):
        validator.accept(final_commit(turn=2))


def test_offline_trace_uses_shared_validator_and_rejects_post_commit_frames():
    frames = [final_commit(), tool_call(turn=2)]
    with pytest.raises(ToolLoopProtocolError, match="follow"):
        evaluate_trace(frames, {"challenge_id": "test", "seed": 1}, set())
