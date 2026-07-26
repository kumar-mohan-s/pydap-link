"""Load and validate a register-map manifest before hardware access."""

from __future__ import annotations

import csv
from pathlib import Path

import pandas as pd

from regmap_model import (
    AccessMode,
    MemoryRange,
    RegisterCheck,
    SafetyClass,
    VerificationMode,
)


REQUIRED_COLUMNS = ("S.No", "Register Name", "Access", "Address", "Value")
SUPPORTED_WIDTHS = (8, 16, 32)


class ManifestValidationError(ValueError):
    """Raised when a manifest cannot safely become an execution plan."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("\n".join(errors))


def load_manifest(path: Path) -> tuple[RegisterCheck, ...]:
    if not path.is_file():
        raise FileNotFoundError(f"Register map not found: {path}")

    suffix = path.suffix.lower()
    if suffix == ".csv":
        _validate_csv_shape(path)
        frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    elif suffix == ".xlsx":
        frame = pd.read_excel(path, dtype=str, keep_default_na=False)
    else:
        raise ManifestValidationError(["Input must be a CSV or XLSX file."])

    frame.columns = [str(column).strip() for column in frame.columns]
    missing = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
    if missing:
        raise ManifestValidationError(
            [f"Missing required column(s): {', '.join(missing)}."]
        )

    checks: list[RegisterCheck] = []
    errors: list[str] = []
    seen_sequences: set[str] = set()
    for index, row in enumerate(frame.to_dict(orient="records"), start=2):
        if _is_blank_row(row):
            continue
        try:
            check = _parse_row(row, index)
            if check.sequence in seen_sequences:
                raise ValueError(f"{check.label}: duplicate S.No value.")
            seen_sequences.add(check.sequence)
            checks.append(check)
        except ValueError as exc:
            errors.append(str(exc))

    if errors:
        raise ManifestValidationError(errors)
    if not checks:
        raise ManifestValidationError(["Register map does not contain any checks."])
    return tuple(checks)


def parse_scratch_range(text: str) -> MemoryRange:
    try:
        start_text, size_text = text.split(":", maxsplit=1)
    except ValueError as exc:
        raise ManifestValidationError(
            ["Scratch range must have the form <start>:<size>, for example 0x2045F000:0x100."]
        ) from exc

    start = _parse_uint(start_text, "scratch range start", "command line", 0xFFFFFFFF)
    size = _parse_uint(size_text, "scratch range size", "command line", 0xFFFFFFFF)
    if size == 0 or start + size > 0x1_0000_0000:
        raise ManifestValidationError(["Scratch range must be non-empty and fit in the 32-bit address space."])
    return MemoryRange(start=start, size=size)


def validate_runtime_policy(
    checks: tuple[RegisterCheck, ...],
    writes_enabled: bool,
    scratch_range: MemoryRange | None,
) -> None:
    writes = [check for check in checks if check.access.writes]
    if not writes:
        return
    if not writes_enabled:
        raise ManifestValidationError(
            ["Manifest contains writes. Re-run with --enable-writes only after reviewing every write."]
        )
    if scratch_range is None:
        raise ManifestValidationError(
            ["Manifest contains writes. Supply an approved --scratch-range <start>:<size>."]
        )

    errors = [
        f"{check.label}: address is outside the approved scratch range."
        for check in writes
        if not scratch_range.contains(check.address, check.width_bits)
    ]
    if errors:
        raise ManifestValidationError(errors)


def _parse_row(row: dict[str, object], csv_line: int) -> RegisterCheck:
    sequence = _cell(row, "S.No")
    name = _cell(row, "Register Name")
    label = f"CSV line {csv_line}"
    if not sequence:
        raise ValueError(f"{label}: S.No is empty.")
    if not name:
        raise ValueError(f"{label}: Register Name is empty.")

    access_text = _cell(row, "Access").upper()
    try:
        access = AccessMode(access_text)
    except ValueError as exc:
        raise ValueError(f"{label}: Access must be R, W, or RW, not '{access_text}'.") from exc

    row_label = f"row {sequence} ({name})"
    address = _parse_uint(_cell(row, "Address"), "Address", row_label, 0xFFFFFFFF)
    width_bits = _parse_uint(_cell(row, "Width") or "32", "Width", row_label, 32)
    if width_bits not in SUPPORTED_WIDTHS:
        raise ValueError(f"{row_label}: Width must be one of {SUPPORTED_WIDTHS} bits.")
    if address % (width_bits // 8):
        raise ValueError(f"{row_label}: Address is not {width_bits}-bit aligned.")

    value = _optional_uint(row, "Value", row_label, width_bits)
    expected = _optional_uint(row, "Expected", row_label, width_bits)
    mask = _optional_uint(row, "Mask", row_label, width_bits)
    verification = _parse_verification(_cell(row, "Verification"), access, row_label)
    safety = _parse_safety(_cell(row, "Safety"), access, row_label)
    requires_halt = _parse_bool(_cell(row, "Requires Halt"), default=True, row_label=row_label)
    restore_after = _parse_bool(
        _cell(row, "Restore"), default=access is AccessMode.READ_WRITE, row_label=row_label
    )

    check = RegisterCheck(
        sequence=sequence,
        name=name,
        access=access,
        address=address,
        width_bits=width_bits,
        value=value,
        expected=expected,
        mask=mask,
        verification=verification,
        safety=safety,
        requires_halt=requires_halt,
        restore_after=restore_after,
    )
    _validate_check(check)
    return check


def _validate_check(check: RegisterCheck) -> None:
    if check.access is AccessMode.READ and check.value is not None:
        raise ValueError(f"{check.label}: a read-only check cannot have a Value.")
    if check.access.writes and check.value is None:
        raise ValueError(f"{check.label}: a write check requires a Value.")
    if check.access.writes and check.safety is not SafetyClass.SCRATCH:
        raise ValueError(f"{check.label}: writes are restricted to Safety=scratch.")
    if check.access is AccessMode.WRITE and check.verification is not VerificationMode.TRANSPORT:
        raise ValueError(f"{check.label}: W checks must use Verification=transport.")
    if check.access is AccessMode.READ_WRITE and check.verification not in (
        VerificationMode.EXACT,
        VerificationMode.MASKED,
    ):
        raise ValueError(f"{check.label}: RW checks must use Verification=exact or masked.")
    if check.access is AccessMode.READ and check.verification is VerificationMode.TRANSPORT:
        raise ValueError(f"{check.label}: read-only checks cannot use Verification=transport.")
    if check.verification is VerificationMode.EXACT and check.expected is None:
        if check.access is AccessMode.READ:
            raise ValueError(f"{check.label}: Verification=exact requires Expected.")
    if check.verification is VerificationMode.MASKED:
        if check.expected is None or check.mask is None:
            raise ValueError(f"{check.label}: Verification=masked requires Expected and Mask.")
    if check.restore_after and check.access is not AccessMode.READ_WRITE:
        raise ValueError(f"{check.label}: Restore is only valid for RW checks.")


def _parse_verification(value: str, access: AccessMode, row_label: str) -> VerificationMode:
    default = VerificationMode.EXACT if access is AccessMode.READ_WRITE else VerificationMode.RECORD
    try:
        return VerificationMode(value.lower() if value else default.value)
    except ValueError as exc:
        choices = ", ".join(mode.value for mode in VerificationMode)
        raise ValueError(f"{row_label}: Verification must be one of {choices}.") from exc


def _parse_safety(value: str, access: AccessMode, row_label: str) -> SafetyClass:
    default = SafetyClass.READ_ONLY if access is AccessMode.READ else SafetyClass.SCRATCH
    try:
        return SafetyClass(value.lower() if value else default.value)
    except ValueError as exc:
        choices = ", ".join(mode.value for mode in SafetyClass)
        raise ValueError(f"{row_label}: Safety must be one of {choices}.") from exc


def _parse_bool(value: str, default: bool, row_label: str) -> bool:
    if not value:
        return default
    values = {"true": True, "yes": True, "1": True, "false": False, "no": False, "0": False}
    try:
        return values[value.lower()]
    except KeyError as exc:
        raise ValueError(f"{row_label}: boolean value must be true/false, yes/no, or 1/0.") from exc


def _optional_uint(
    row: dict[str, object], column: str, row_label: str, width_bits: int
) -> int | None:
    value = _cell(row, column)
    if not value:
        return None
    return _parse_uint(value, column, row_label, (1 << width_bits) - 1)


def _parse_uint(value: str, field: str, row_label: str, maximum: int) -> int:
    text = value.strip()
    if not text:
        raise ValueError(f"{row_label}: {field} is empty.")
    try:
        base = 16 if text.lower().startswith("0x") else 10
        parsed = int(text, base)
    except ValueError as exc:
        raise ValueError(f"{row_label}: could not parse {field}='{text}'.") from exc
    if not 0 <= parsed <= maximum:
        raise ValueError(f"{row_label}: {field} must be between 0 and 0x{maximum:X}.")
    return parsed


def _cell(row: dict[str, object], column: str) -> str:
    value = row.get(column, "")
    return "" if value is None else str(value).strip()


def _is_blank_row(row: dict[str, object]) -> bool:
    return not any(_cell(row, column) for column in REQUIRED_COLUMNS)


def _validate_csv_shape(path: Path) -> None:
    with path.open("r", encoding="utf-8-sig", newline="") as source:
        rows = csv.reader(source)
        try:
            header = next(rows)
        except StopIteration as exc:
            raise ManifestValidationError(["CSV file is empty."]) from exc

        expected_fields = len(header)
        errors = [
            f"CSV line {line_number}: expected {expected_fields} fields, found {len(row)}. "
            "Quote fields that contain commas."
            for line_number, row in enumerate(rows, start=2)
            if row and len(row) != expected_fields
        ]
    if errors:
        raise ManifestValidationError(errors)
