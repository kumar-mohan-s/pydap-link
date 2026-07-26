"""Approved, non-destructive register profiles for known targets."""

from __future__ import annotations

from dataclasses import dataclass

from regmap_manifest import ManifestValidationError
from regmap_model import AccessMode, RegisterCheck, SafetyClass, VerificationMode


@dataclass(frozen=True)
class ApprovedRegister:
    name: str
    address: int
    width_bits: int
    access: AccessMode
    verification: VerificationMode
    expected: int | None = None
    mask: int | None = None


@dataclass(frozen=True)
class TargetProfile:
    name: str
    description: str
    source: str
    registers: tuple[ApprovedRegister, ...]

    def validate(self, checks: tuple[RegisterCheck, ...]) -> None:
        approved = {register.address: register for register in self.registers}
        errors: list[str] = []
        for check in checks:
            reference = approved.get(check.address)
            if reference is None:
                errors.append(f"{check.label}: address is not approved by profile '{self.name}'.")
                continue
            if check.name != reference.name:
                errors.append(f"{check.label}: Register Name must be '{reference.name}'.")
            if check.access is not reference.access or check.width_bits != reference.width_bits:
                errors.append(f"{check.label}: access width or mode differs from the approved profile entry.")
            if check.verification is not reference.verification:
                errors.append(f"{check.label}: verification rule differs from the approved profile entry.")
            if check.expected != reference.expected or check.mask != reference.mask:
                errors.append(f"{check.label}: expected value or mask differs from the approved profile entry.")
            if check.safety is not SafetyClass.READ_ONLY:
                errors.append(f"{check.label}: current target profiles only permit read-only checks.")
        if errors:
            raise ManifestValidationError(errors)


_CPUID = ApprovedRegister(
    name="SCB_CPUID",
    address=0xE000ED00,
    width_bits=32,
    access=AccessMode.READ,
    verification=VerificationMode.MASKED,
    expected=0x410FC270,
    mask=0xFF0FFFF0,
)

_SAMV71Q21 = TargetProfile(
    name="samv71q21",
    description="ATSAMV71Q21 non-destructive initial bring-up checks",
    source=(
        "Atmel SAMV71 DFP 3.0.214: ATSAMV71Q21.svd and generated component headers"
    ),
    registers=(
        ApprovedRegister(
            name="CHIPID_CIDR",
            address=0x400E0940,
            width_bits=32,
            access=AccessMode.READ,
            verification=VerificationMode.MASKED,
            expected=0x01220E00,
            mask=0x0FFF0FE0,
        ),
        ApprovedRegister(
            name="CHIPID_EXID",
            address=0x400E0944,
            width_bits=32,
            access=AccessMode.READ,
            verification=VerificationMode.RECORD,
        ),
        _CPUID,
        ApprovedRegister(
            name="RSTC_SR",
            address=0x400E1804,
            width_bits=32,
            access=AccessMode.READ,
            verification=VerificationMode.RECORD,
        ),
        ApprovedRegister(
            name="PMC_SR",
            address=0x400E0668,
            width_bits=32,
            access=AccessMode.READ,
            verification=VerificationMode.RECORD,
        ),
    ),
)

_CORTEX_M7 = TargetProfile(
    name="cortex-m7",
    description="Architecture-level Cortex-M7 core identity check",
    source="ARMv7-M System Control Space CPUID register",
    registers=(_CPUID,),
)

_CORTEX_M = TargetProfile(
    name="cortex-m",
    description="Architecture-level Cortex-M CPUID snapshot",
    source="ARM Cortex-M System Control Space CPUID register",
    registers=(
        ApprovedRegister(
            name="SCB_CPUID",
            address=0xE000ED00,
            width_bits=32,
            access=AccessMode.READ,
            verification=VerificationMode.RECORD,
        ),
    ),
)

_PROFILES = {
    profile.name: profile
    for profile in (_SAMV71Q21, _CORTEX_M, _CORTEX_M7)
}


def get_profile(name: str) -> TargetProfile:
    try:
        return _PROFILES[name]
    except KeyError as exc:
        available = ", ".join(sorted(_PROFILES))
        raise ManifestValidationError(
            [f"Unknown profile '{name}'. Available profiles: {available}."]
        ) from exc


def profile_names() -> tuple[str, ...]:
    return tuple(sorted(_PROFILES))
