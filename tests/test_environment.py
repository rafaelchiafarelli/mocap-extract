import subprocess
import sys

import mocap_extract


def test_cli_version():
    result = subprocess.run(
        [sys.executable, "-c", "from mocap_extract.cli import main; main(['--version'])"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert result.stdout.strip() == f"mocap-extract {mocap_extract.__version__}"


def test_python_is_312():
    assert sys.version_info[:2] == (3, 12)


def test_freemocap_pinned_and_headless_api_importable():
    # Fresh interpreter: FreeMoCap 1.8.2 hits a circular import when the root
    # logger already has handlers at import time (pytest installs its own).
    code = (
        "from importlib.metadata import version\n"
        "from freemocap.core_processes.process_motion_capture_videos.process_recording_headless"
        " import process_recording_headless\n"
        "assert callable(process_recording_headless)\n"
        "print(version('freemocap'))\n"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().splitlines()[-1] == "1.8.2"


def test_mocap_contracts_importable():
    import mocap_contracts

    assert mocap_contracts
