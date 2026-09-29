"""Validation for a single queued submission record.

Mirrors a JS implementation of the same rules, but kept as a plain
function returning a list of error strings (empty = valid) rather than
raising, so a batch can validate every record and separate the good
ones from the bad ones at sync time.
"""
from __future__ import annotations

import uuid
from datetime import datetime

PDP_STATUSES = {"Active", "Expiring", "Missing"}


def _parse_timestamp(value: str) -> datetime:
    # Python's fromisoformat only accepts "Z" from 3.11+; normalize for
    # compatibility with older interpreters too.
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def validate_record(record: dict) -> list[str]:
    errors: list[str] = []

    if not isinstance(record, dict):
        return ["record must be an object"]

    submission_uuid = record.get("submission_uuid")
    if not isinstance(submission_uuid, str):
        errors.append("submission_uuid must be a valid UUID")
    else:
        try:
            uuid.UUID(submission_uuid)
        except ValueError:
            errors.append("submission_uuid must be a valid UUID")

    urban_council = record.get("urban_council")
    if not isinstance(urban_council, str) or not urban_council.strip():
        errors.append("urban_council must be a non-empty string")

    pdp_status = record.get("pdp_status")
    if pdp_status not in PDP_STATUSES:
        errors.append(f"pdp_status must be one of {', '.join(sorted(PDP_STATUSES))}")

    # Cross-field rule: a missing PDP has no expiry; otherwise a year is required.
    expiry_year = record.get("expiry_year")
    if pdp_status == "Missing":
        if expiry_year is not None:
            errors.append("expiry_year must be null when pdp_status is Missing")
    elif pdp_status in PDP_STATUSES:
        if (
            not isinstance(expiry_year, int)
            or isinstance(expiry_year, bool)
            or not (2000 <= expiry_year <= 2100)
        ):
            errors.append("expiry_year must be an integer between 2000 and 2100")

    timestamp = record.get("field_officer_timestamp")
    if not isinstance(timestamp, str):
        errors.append("field_officer_timestamp must be an ISO-8601 timestamp")
    else:
        try:
            _parse_timestamp(timestamp)
        except ValueError:
            errors.append("field_officer_timestamp must be an ISO-8601 timestamp")

    return errors
