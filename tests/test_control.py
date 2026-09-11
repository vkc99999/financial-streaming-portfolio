import importlib.util
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("control", Path(__file__).resolve().parents[1] / "scripts/control.py")
control = importlib.util.module_from_spec(spec)
spec.loader.exec_module(control)


class DockerPreflightTests(unittest.TestCase):
    def test_accepts_a_responsive_engine(self):
        with patch.object(control.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, '"28.0.1"\n', "")):
            control.require_engine()

    def test_rejects_empty_server_version_even_with_zero_exit(self):
        # Docker templates can report exit 0 despite a daemon error on stderr.
        with patch.object(control.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, '""\n', "daemon unavailable")):
            with self.assertRaisesRegex(RuntimeError, "unavailable"):
                control.require_engine()

    def test_timeout_becomes_actionable_error(self):
        with patch.object(control.subprocess, "run", side_effect=subprocess.TimeoutExpired("docker", 15)):
            with self.assertRaisesRegex(RuntimeError, "15 seconds"):
                control.require_engine()


if __name__ == "__main__":
    unittest.main()
