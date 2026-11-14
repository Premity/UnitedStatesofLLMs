"""Prepared cases for the question form's picker.

A case file holds the tribunal's holding and outcome. Only `Case.public()` is
ever returned, and the response models here are `PublicCase`, so a field added
to `Case` later does not reach the browser unless it is added to `PublicCase`
on purpose (ADR 0013).
"""

from __future__ import annotations

import json
from pathlib import Path

import structlog
from fastapi import APIRouter, HTTPException
from pydantic import ValidationError

from app.core.config import get_settings
from council_core.models.case import Case, PublicCase

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/cases", tags=["cases"])


def load_public_cases(directory: Path) -> list[PublicCase]:
    """Read every `*.json` case in `directory`, keeping only the public view.

    A file that does not parse is logged and skipped rather than failing the
    list: one bad fixture should not take the picker away.
    """
    cases: list[PublicCase] = []
    for path in sorted(directory.glob("*.json")):
        try:
            case = Case.model_validate(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError, ValidationError):
            log.warning("case_file_unreadable", path=str(path))
            continue
        cases.append(case.public())
    return cases


@router.get("", response_model=list[PublicCase])
async def list_cases() -> list[PublicCase]:
    """Every prepared case, question and facts only."""
    return load_public_cases(get_settings().cases_dir)


@router.get("/{case_id}", response_model=PublicCase)
async def get_case(case_id: str) -> PublicCase:
    """One prepared case, question and facts only."""
    for case in load_public_cases(get_settings().cases_dir):
        if case.id == case_id:
            return case
    raise HTTPException(status_code=404, detail=f"No case '{case_id}'.")
