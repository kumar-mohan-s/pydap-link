"""Lazy pyOCD adapter that preserves the target's initial run state."""

from __future__ import annotations

from dataclasses import dataclass
from importlib.metadata import version
from pathlib import Path


@dataclass
class PyOcdConnection:
    target_override: str
    probe_uid: str | None
    pack_path: Path | None = None
    session: object | None = None
    target: object | None = None
    initial_state: str = "UNKNOWN"
    final_state: str = "UNKNOWN"
    halted_by_scanner: bool = False
    probe_description: str = ""
    selected_probe_uid: str = ""
    target_part_number: str = ""

    def __enter__(self) -> "PyOcdConnection":
        from pyocd.core.helpers import ConnectHelper

        options = self._build_session_options()
        self.session = ConnectHelper.session_with_chosen_probe(
            blocking=False,
            return_first=False,
            unique_id=self.probe_uid,
            auto_open=False,
            target_override=self.target_override,
            options=options,
        )
        if self.session is None:
            raise RuntimeError(
                "No eligible debug probe found. Check the USB connection and probe UID."
            )

        self.session.open()
        self.target = self.session.board.target
        probe = self.session.probe
        self.probe_description = str(getattr(probe, "description", "unknown"))
        self.selected_probe_uid = str(getattr(probe, "unique_id", "unknown"))
        self.target_part_number = str(getattr(self.target, "part_number", "unknown"))
        self.initial_state = self._state()
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        try:
            if self.halted_by_scanner and self.target is not None:
                self.target.resume()
            if self.target is not None:
                self.final_state = self._state()
        finally:
            if self.session is not None:
                self.session.close()

    def halt_if_needed(self, checks_require_halt: bool) -> None:
        if not checks_require_halt or self.initial_state == "HALTED":
            return
        assert self.target is not None
        self.target.halt()
        if self._state() != "HALTED":
            raise RuntimeError("pyOCD did not report a halted core after the halt request.")
        self.halted_by_scanner = True

    def read_memory(self, address: int, width_bits: int) -> int:
        assert self.target is not None
        method = {8: "read8", 16: "read16", 32: "read32"}[width_bits]
        return int(getattr(self.target, method)(address))

    def write_memory(self, address: int, value: int, width_bits: int) -> None:
        assert self.target is not None
        method = {8: "write8", 16: "write16", 32: "write32"}[width_bits]
        getattr(self.target, method)(address, value)

    def metadata(self) -> dict[str, str]:
        return {
            "pyOCD Version": version("pyocd"),
            "Target Override": self.target_override,
            "Target Part Number": self.target_part_number,
            "Probe Description": self.probe_description,
            "Probe UID": self.selected_probe_uid,
        }

    def _build_session_options(self) -> dict[str, object]:
        # pyOCD otherwise halts on connect and resumes on disconnect, masking the true initial state.
        options: dict[str, object] = {
            "connect_mode": "attach",
            "resume_on_disconnect": False,
        }
        if self.pack_path:
            options["pack"] = str(self.pack_path)
        return options

    def _state(self) -> str:
        assert self.target is not None
        state = self.target.get_state()
        return str(getattr(state, "name", state)).upper()
