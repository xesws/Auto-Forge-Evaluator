"""SuperNI-style normalized exact match. Token-F1 in note only."""

from __future__ import annotations

from src.verifiers.qa_em import verify as qa_verify


def verify(output: str, reference: dict) -> dict:
    return qa_verify(output, reference)
