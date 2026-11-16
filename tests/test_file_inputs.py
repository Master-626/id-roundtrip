import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from id_roundtrip import AuditError, audit

class FileInputTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.good = self.root / 'good.csv'
        self.good.write_text('key,id\na,001\n')

    def run_cli(self, path):
        return subprocess.run([sys.executable, '-m', 'id_roundtrip', str(path), str(self.good),
                               '--key', 'key', '--field', 'id'], capture_output=True, timeout=3)

    def test_directory_rejected(self):
        result = self.run_cli(self.root)
        self.assertEqual(result.returncode, 2)
        self.assertNotIn(str(self.root).encode(), result.stderr)

    @unittest.skipUnless(hasattr(os, 'mkfifo'), 'POSIX named pipe')
    def test_fifo_rejected_without_writer(self):
        fifo = self.root / 'pipe'
        os.mkfifo(fifo)
        result = self.run_cli(fifo)
        self.assertEqual(result.returncode, 2)
        self.assertIn(b'regular file', result.stderr)

    @unittest.skipUnless(os.name == 'posix', 'POSIX special device')
    def test_device_rejected(self):
        self.assertEqual(self.run_cli('/dev/zero').returncode, 2)

    @unittest.skipUnless(hasattr(os, 'mkfifo'), 'POSIX named pipe')
    def test_descriptor_verified_after_path_check(self):
        fifo = self.root / 'pipe'
        os.mkfifo(fifo)
        original_open = os.open
        def replaced_open(path, flags):
            return original_open(fifo, flags)
        with patch('id_roundtrip.os.open', side_effect=replaced_open):
            with self.assertRaises(AuditError):
                audit(self.good, self.good, keys=['key'], fields=['id'])

    def test_missing_file_cli_redacts_path(self):
        result = self.run_cli(self.root / 'secret-name.csv')
        self.assertEqual(result.returncode, 2)
        self.assertNotIn(b'secret-name', result.stderr)
