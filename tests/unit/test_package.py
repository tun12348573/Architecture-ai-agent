import subprocess
import sys


def test_version_flag():
    result = subprocess.run(
        [sys.executable, "-m", "exterior_agent", "--version"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "0.1.0" in result.stdout
