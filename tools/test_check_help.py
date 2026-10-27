import subprocess
import sys
import unittest

class TestCheckHelp(unittest.TestCase):
    def test_help_describes_shared_qemu_cache(self):
        """Ensure check --help accurately documents shared QEMU cache location."""
        res = subprocess.run([sys.executable, "tools/check", "--help"], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        output = res.stdout
        
        self.assertIn("Project work is kept in", output)
        self.assertIn("shared base disk and downloaded", output)
        self.assertIn("relocatable via XDG_CACHE_HOME", output)
        self.assertIn("with --qemu, shared base disk remains in", output)

if __name__ == "__main__":
    unittest.main()
