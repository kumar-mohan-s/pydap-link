from __future__ import annotations

import unittest
from pathlib import Path

from regmap_pyocd import PyOcdConnection


class PyOcdConnectionTests(unittest.TestCase):
    def test_session_options_preserve_target_run_state(self) -> None:
        connection = PyOcdConnection("atsamv71q21", "probe-id")

        self.assertEqual(
            connection._build_session_options(),
            {"connect_mode": "attach", "resume_on_disconnect": False},
        )

    def test_session_options_include_requested_device_pack(self) -> None:
        pack = Path("C:/packs/SAM-V.pack")
        connection = PyOcdConnection("atsamv71q21", "probe-id", pack)

        self.assertEqual(connection._build_session_options()["pack"], str(pack))


if __name__ == "__main__":
    unittest.main()
