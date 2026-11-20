"""Run the existing full import/sync/recovery checks against disposable storage."""
import os
import subprocess
import sys

from conftest import ROOT


def test_hosted_import_sync_recovery(reader_environment, browser_channel):
    result = subprocess.run(
        [sys.executable, str(ROOT / 'tests/original_reader_test.py'),
         '--base-url', reader_environment['base']],
        env=dict(os.environ, READER_BROWSER_CHANNEL=browser_channel or ''),
        capture_output=True, text=True, timeout=180,
    )
    assert result.returncode == 0, result.stdout + result.stderr
