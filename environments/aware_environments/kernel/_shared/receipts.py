"""Helpers for turning Receipt objects into serialisable payloads."""

from __future__ import annotations

from typing import Any, Dict, Mapping

from aware_environment.fs.receipt import EnsureOp, MoveOp, Receipt, WriteOp


def receipt_to_dict(receipt: Receipt) -> Dict[str, Any]:
    """Convert a Receipt into a JSON-serialisable dictionary."""
    context = getattr(receipt, "context", None)
    return {
        "schema": getattr(receipt, "schema", None),
        "timestamp": getattr(receipt, "timestamp", None).isoformat() if getattr(receipt, "timestamp", None) else None,
        "context": {
            "object_type": getattr(context, "object_type", None),
            "function": getattr(context, "function", None),
            "selectors": dict(getattr(context, "selectors", {}) or {}),
        },
        "fs_ops": [
            _fs_op_to_dict(op)
            for op in getattr(receipt, "fs_ops", ())
        ],
        "policy_decisions": [
            {
                "path": str(getattr(decision, "path", "")),
                "action": getattr(decision, "action", None),
                "policy": getattr(decision, "policy", None),
                "result": getattr(decision, "result", None),
                "message": getattr(decision, "message", None),
            }
            for decision in getattr(receipt, "policy_decisions", ())
        ],
        "hooks": [
            {
                "name": getattr(log, "name", None),
                "path": str(getattr(log, "path", "")) if getattr(log, "path", None) else None,
                "status": getattr(log, "status", None),
                "error": getattr(log, "error", None),
            }
            for log in getattr(receipt, "hooks", ())
        ],
    }


def receipt_to_journal_entry(receipt_dict: Mapping[str, Any]) -> Dict[str, Any]:
    """Derive a compact journal entry from a receipt dictionary."""
    context = receipt_dict.get("context") or {}
    fs_ops = receipt_dict.get("fs_ops") or []
    writes = [op for op in fs_ops if isinstance(op, Mapping) and op.get("type") == "write"]
    return {
        "action": "apply-plan",
        "object_type": context.get("object_type"),
        "function": context.get("function"),
        "selectors": dict(context.get("selectors") or {}),
        "writes": [
            {key: value for key, value in write.items() if key in {"path", "event", "doc_type", "policy"}}
            for write in writes
            if isinstance(write, Mapping)
        ],
        "timestamp": receipt_dict.get("timestamp"),
    }


def _fs_op_to_dict(op: Any) -> dict[str, Any]:
    if isinstance(op, WriteOp):
        return {
            "type": "write",
            "path": str(op.path),
            "event": op.event,
            "policy": op.policy,
            "doc_type": op.doc_type,
            "content_hash": op.content_hash,
            "metadata": dict(op.metadata),
            "hook_metadata": dict(op.hook_metadata),
            "timestamp": op.timestamp.isoformat().replace("+00:00", "Z") if op.timestamp else None,
        }
    if isinstance(op, MoveOp):
        return {
            "type": "move",
            "src": str(op.src),
            "dest": str(op.dest),
            "overwrite": op.overwrite,
            "metadata": dict(op.metadata),
        }
    if isinstance(op, EnsureOp):
        return {
            "type": "ensure",
            "path": str(op.path),
            "metadata": dict(op.metadata),
        }
    if isinstance(op, Mapping):
        return dict(op)
    return {}


__all__ = ["receipt_to_dict", "receipt_to_journal_entry"]
