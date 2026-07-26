"""Domain types for the register-map scanner."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class AccessMode(str, Enum):
    READ = "R"
    WRITE = "W"
    READ_WRITE = "RW"

    @property
    def reads(self) -> bool:
        return self in (AccessMode.READ, AccessMode.READ_WRITE)

    @property
    def writes(self) -> bool:
        return self in (AccessMode.WRITE, AccessMode.READ_WRITE)


class VerificationMode(str, Enum):
    RECORD = "record"
    EXACT = "exact"
    MASKED = "masked"
    TRANSPORT = "transport"


class SafetyClass(str, Enum):
    READ_ONLY = "read_only"
    SCRATCH = "scratch"


class ResultStatus(str, Enum):
    PASS = "PASS"
    TRANSPORT_ONLY = "PASS_TRANSPORT_ONLY"
    FAIL = "FAIL"


@dataclass(frozen=True)
class MemoryRange:
    start: int
    size: int

    @property
    def end(self) -> int:
        return self.start + self.size

    def contains(self, address: int, width_bits: int) -> bool:
        return self.start <= address and address + width_bits // 8 <= self.end


@dataclass(frozen=True)
class RegisterCheck:
    sequence: str
    name: str
    access: AccessMode
    address: int
    width_bits: int
    value: int | None
    expected: int | None
    mask: int | None
    verification: VerificationMode
    safety: SafetyClass
    requires_halt: bool
    restore_after: bool

    @property
    def label(self) -> str:
        return f"row {self.sequence} ({self.name})"


@dataclass
class ScanResult:
    check: RegisterCheck
    status: ResultStatus
    detail: str
    observed_value: int | None = None
    written_value: int | None = None
    original_value: int | None = None
    restored_value: int | None = None


def format_hex(value: int | None, width_bits: int = 32) -> str:
    if value is None:
        return ""
    return f"0x{value:0{width_bits // 4}X}"
