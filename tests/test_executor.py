from __future__ import annotations

import unittest

from regmap_executor import execute_scan
from regmap_model import (
    AccessMode,
    RegisterCheck,
    ResultStatus,
    SafetyClass,
    VerificationMode,
)


class MemoryTarget:
    def __init__(self, memory: dict[int, int]) -> None:
        self.memory = memory
        self.writes: list[tuple[int, int, int]] = []

    def read_memory(self, address: int, width_bits: int) -> int:
        return self.memory[address]

    def write_memory(self, address: int, value: int, width_bits: int) -> None:
        self.memory[address] = value
        self.writes.append((address, value, width_bits))


class ExecutorTests(unittest.TestCase):
    def test_cpuid_mask_allows_core_variant_and_revision(self) -> None:
        check = RegisterCheck(
            sequence="0",
            name="SCB_CPUID",
            access=AccessMode.READ,
            address=0xE000ED00,
            width_bits=32,
            value=None,
            expected=0x410FC270,
            mask=0xFF0FFFF0,
            verification=VerificationMode.MASKED,
            safety=SafetyClass.READ_ONLY,
            requires_halt=True,
            restore_after=False,
        )

        result = execute_scan((check,), MemoryTarget({check.address: 0x410FC271}))[0]

        self.assertEqual(result.status, ResultStatus.PASS)

    def test_masked_read_verifies_selected_bits(self) -> None:
        check = RegisterCheck(
            sequence="1",
            name="CIDR",
            access=AccessMode.READ,
            address=0x400E0940,
            width_bits=32,
            value=None,
            expected=0x01220E00,
            mask=0x0FFF0FE0,
            verification=VerificationMode.MASKED,
            safety=SafetyClass.READ_ONLY,
            requires_halt=True,
            restore_after=False,
        )

        result = execute_scan((check,), MemoryTarget({check.address: 0x01220E1F}))[0]

        self.assertEqual(result.status, ResultStatus.PASS)

    def test_scratch_write_is_verified_and_restored(self) -> None:
        check = RegisterCheck(
            sequence="2",
            name="Scratch",
            access=AccessMode.READ_WRITE,
            address=0x2045F000,
            width_bits=32,
            value=0xDEADBEEF,
            expected=None,
            mask=None,
            verification=VerificationMode.EXACT,
            safety=SafetyClass.SCRATCH,
            requires_halt=True,
            restore_after=True,
        )
        target = MemoryTarget({check.address: 0xCAFEBABE})

        result = execute_scan((check,), target)[0]

        self.assertEqual(result.status, ResultStatus.PASS)
        self.assertEqual(result.observed_value, 0xDEADBEEF)
        self.assertEqual(result.restored_value, 0xCAFEBABE)
        self.assertEqual(target.memory[check.address], 0xCAFEBABE)


if __name__ == "__main__":
    unittest.main()
