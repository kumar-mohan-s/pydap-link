"""Execute validated checks through a small target-memory interface."""

from __future__ import annotations

from typing import Protocol

from regmap_model import (
    AccessMode,
    RegisterCheck,
    ResultStatus,
    ScanResult,
    VerificationMode,
    format_hex,
)


class TargetMemory(Protocol):
    def read_memory(self, address: int, width_bits: int) -> int: ...

    def write_memory(self, address: int, value: int, width_bits: int) -> None: ...


def execute_scan(checks: tuple[RegisterCheck, ...], target: TargetMemory) -> list[ScanResult]:
    return [_execute_check(check, target) for check in checks]


def summarize(results: list[ScanResult]) -> dict[str, int]:
    return {
        "total": len(results),
        "passed": sum(result.status is ResultStatus.PASS for result in results),
        "transport_only": sum(
            result.status is ResultStatus.TRANSPORT_ONLY for result in results
        ),
        "failed": sum(result.status is ResultStatus.FAIL for result in results),
    }


def _execute_check(check: RegisterCheck, target: TargetMemory) -> ScanResult:
    if check.access is AccessMode.READ:
        return _read_check(check, target)
    return _write_check(check, target)


def _read_check(check: RegisterCheck, target: TargetMemory) -> ScanResult:
    try:
        observed = target.read_memory(check.address, check.width_bits)
        passed, detail = _verify(check, observed)
        return ScanResult(
            check=check,
            status=ResultStatus.PASS if passed else ResultStatus.FAIL,
            detail=detail,
            observed_value=observed,
        )
    except Exception as exc:  # A failed register must not discard later evidence.
        return _failure(check, exc)


def _write_check(check: RegisterCheck, target: TargetMemory) -> ScanResult:
    original: int | None = None
    observed: int | None = None
    restored: int | None = None
    status = ResultStatus.FAIL
    detail = "Write did not complete."

    try:
        if check.restore_after:
            original = target.read_memory(check.address, check.width_bits)
        target.write_memory(check.address, check.value or 0, check.width_bits)

        if check.access is AccessMode.WRITE:
            status = ResultStatus.TRANSPORT_ONLY
            detail = "Write completed; write-only register has no read-back verification."
        else:
            observed = target.read_memory(check.address, check.width_bits)
            passed, detail = _verify(check, observed)
            status = ResultStatus.PASS if passed else ResultStatus.FAIL
    except Exception as exc:  # A restore is still attempted when an original value was read.
        detail = f"{type(exc).__name__}: {exc}"
    finally:
        if original is not None:
            try:
                target.write_memory(check.address, original, check.width_bits)
                restored = target.read_memory(check.address, check.width_bits)
                if restored != original:
                    status = ResultStatus.FAIL
                    detail = (
                        f"Restore mismatch: expected {format_hex(original, check.width_bits)}, "
                        f"observed {format_hex(restored, check.width_bits)}."
                    )
            except Exception as exc:
                status = ResultStatus.FAIL
                detail = f"Restore failed: {type(exc).__name__}: {exc}"

    return ScanResult(
        check=check,
        status=status,
        detail=detail,
        observed_value=observed,
        written_value=check.value,
        original_value=original,
        restored_value=restored,
    )


def _verify(check: RegisterCheck, observed: int) -> tuple[bool, str]:
    if check.verification is VerificationMode.RECORD:
        return True, "Observed dynamic value."
    if check.verification is VerificationMode.EXACT:
        expected = check.expected if check.expected is not None else check.value
        assert expected is not None
        passed = observed == expected
        return passed, _comparison_detail("Exact", observed, expected, check.width_bits)
    if check.verification is VerificationMode.MASKED:
        assert check.expected is not None and check.mask is not None
        passed = (observed & check.mask) == (check.expected & check.mask)
        detail = _comparison_detail("Masked", observed, check.expected, check.width_bits)
        return passed, f"{detail} Mask={format_hex(check.mask, check.width_bits)}."
    return False, "Transport-only verification is not valid for a readable register."


def _comparison_detail(kind: str, observed: int, expected: int, width_bits: int) -> str:
    return (
        f"{kind} comparison: observed {format_hex(observed, width_bits)}, "
        f"expected {format_hex(expected, width_bits)}."
    )


def _failure(check: RegisterCheck, exc: Exception) -> ScanResult:
    return ScanResult(
        check=check,
        status=ResultStatus.FAIL,
        detail=f"{type(exc).__name__}: {exc}",
    )
