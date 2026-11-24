"""CLI status, broken-pipe handling, and the setuptools metadata fix."""
import errno
import io
import os
import subprocess
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import pytest

from id_roundtrip import __version__
from id_roundtrip.__main__ import main

ROOT = Path(__file__).resolve().parents[1]


def _run(argv):
    stdout, stderr = io.StringIO(), io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        code = main(argv)
    return code, stdout.getvalue(), stderr.getvalue()


def _closed_stdout(argv):
    """Run the CLI with the stdout read-end already closed."""
    read_fd, write_fd = os.pipe()
    os.close(read_fd)
    env = os.environ.copy()
    src = str(ROOT / "src")
    previous = env.get("PYTHONPATH")
    env["PYTHONPATH"] = src if not previous else src + os.pathsep + previous
    proc = subprocess.Popen(
        [sys.executable, "-m", "id_roundtrip", *argv],
        stdout=write_fd,
        stderr=subprocess.PIPE,
        env=env,
    )
    os.close(write_fd)
    stderr = proc.stderr.read()
    return proc.wait(timeout=10), stderr


def test_main_status_codes(tmp_path):
    reference = tmp_path / "reference.csv"
    observed = tmp_path / "observed.csv"
    reference.write_text("key,id\nx,001\n", encoding="utf-8")
    observed.write_text("key,id\nx,001\n", encoding="utf-8")
    code, out, err = _run([str(reference), str(observed), "--key", "key", "--field", "id"])
    assert code == 0 and err == "" and '"ok": true' in out

    observed.write_text("key,id\nx,1\n", encoding="utf-8")
    code, out, err = _run([str(reference), str(observed), "--key", "key", "--field", "id"])
    assert code == 1 and err == "" and '"kind": "leading_zeros"' in out

    observed.write_text("key,id\nx\n", encoding="utf-8")
    code, _out, err = _run([str(reference), str(observed), "--key", "key", "--field", "id"])
    assert code == 2
    assert err.strip() == "id-roundtrip: record 1: inconsistent column count"
    assert "x" not in err


def test_missing_file_stays_redacted(tmp_path):
    good = tmp_path / "good.csv"
    good.write_text("key,id\na,001\n", encoding="utf-8")
    missing = tmp_path / "secret-name.csv"
    code, _out, err = _run([str(missing), str(good), "--key", "key", "--field", "id"])
    assert code == 2
    assert err.strip() == "id-roundtrip: could not read input file"
    assert "secret-name" not in err


def test_windows_closed_pipe_is_not_a_posix_einval(monkeypatch):
    from id_roundtrip.__main__ import _output_pipe_closed

    closed = OSError(errno.EINVAL, "invalid argument")
    closed.winerror = 232
    monkeypatch.setattr(os, "name", "nt")
    assert _output_pipe_closed(closed) is True
    monkeypatch.setattr(os, "name", "posix")
    assert _output_pipe_closed(OSError(errno.EINVAL, "invalid argument")) is False
    assert _output_pipe_closed(BrokenPipeError()) is True


def test_closed_stdout_keeps_audit_status(tmp_path):
    reference = tmp_path / "reference.csv"
    observed = tmp_path / "observed.csv"
    reference.write_text("key,id\nok,001\n", encoding="utf-8")
    observed.write_text("key,id\nok,001\n", encoding="utf-8")
    code, stderr = _closed_stdout([str(reference), str(observed), "--key", "key", "--field", "id"])
    assert code == 0
    assert b"could not read input file" not in stderr
    assert b"BrokenPipe" not in stderr
    assert b"Exception ignored" not in stderr

    rows = ["key,id"] + [f"r{i},{i:04d}" for i in range(400)]
    other = ["key,id"] + [f"r{i},{i}" for i in range(400)]
    reference.write_text("\n".join(rows) + "\n", encoding="utf-8")
    observed.write_text("\n".join(other) + "\n", encoding="utf-8")
    code, stderr = _closed_stdout([str(reference), str(observed), "--key", "key", "--field", "id"])
    assert code == 1
    assert b"could not read input file" not in stderr
    assert b"BrokenPipe" not in stderr
    assert b"Exception ignored" not in stderr


def test_wheel_builds_on_declared_setuptools(tmp_path):
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'license = {text = "MIT"}' in pyproject
    assert f'version = "{__version__}"' in pyproject
    # --no-build-isolation uses the interpreter's setuptools. GitHub's
    # setup-python images do not ship it; the dev extra does.
    pytest.importorskip("setuptools")
    result = subprocess.run(
        [
            sys.executable, "-m", "pip", "wheel", "--no-deps", "--no-build-isolation",
            "--disable-pip-version-check", str(ROOT), "-w", str(tmp_path),
        ],
        capture_output=True, text=True, timeout=120, check=False,
    )
    assert result.returncode == 0, result.stderr
    wheels = list(tmp_path.glob(f"id_roundtrip-{__version__}-*.whl"))
    assert len(wheels) == 1
