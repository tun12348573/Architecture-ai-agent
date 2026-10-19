"""Shared validation constants and issue type (kept separate to avoid import cycles)."""

from typing import NamedTuple

TOL = 0.001
MIN_INTERIOR = 0.5
MIN_LINTEL = 0.10
MIN_PIER = 0.10


class ValidationIssue(NamedTuple):
    path: str
    message: str
