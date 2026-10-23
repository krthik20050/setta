import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.paths import PROJECT_ROOT
from src.single_instance import acquire_instance, release_instance


@unittest.skipUnless(os.name == 'nt', 'Windows instance guard')
class SingleInstanceTests(unittest.TestCase):
    def test_second_owner_signals_first_without_acquiring_and_release_allows_restart(self):
        parent = PROJECT_ROOT / 'runtime' / 'instance-tests'
        parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=parent) as folder:
            location = Path(folder)
            with patch('src.single_instance.PROJECT_ROOT', location), patch('src.single_instance.RUNTIME_DIR', location):
                handle, acquired = acquire_instance()
                self.assertTrue(acquired)
                try:
                    duplicate, acquired = acquire_instance()
                    self.assertFalse(acquired)
                    self.assertIsNone(duplicate)
                    self.assertEqual((location / '.open-hub').read_text(), 'open')
                finally:
                    release_instance(handle)
                restarted, acquired = acquire_instance()
                try:
                    self.assertTrue(acquired)
                finally:
                    release_instance(restarted)
