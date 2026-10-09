"""CLI regression checks; external builds and Docker execution are mocked."""
import contextlib
import importlib.machinery
import importlib.util
import io
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
loader = importlib.machinery.SourceFileLoader("scanner_check", str(ROOT / "tools/check"))
spec = importlib.util.spec_from_loader(loader.name, loader)
check = importlib.util.module_from_spec(spec)
loader.exec_module(check)


class DockerShellStatusTest(unittest.TestCase):
    def run_check(self, docker_status=0, no_shell=False, build_error=None):
        scratch = ROOT / "scratch"
        scratch.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as temporary:
            base = pathlib.Path(temporary)
            project = base / "demo"
            project.mkdir()
            (project / "project.yaml").write_text(
                "repo: https://example.org/demo\n"
                "primary_contact: security@example.org\n"
                "dockerfile: Dockerfile\n", encoding="utf-8"
            )
            argv = ["tools/check", str(project), "--dir", str(base / "work")]
            if no_shell:
                argv.append("--no-shell")
            with patch.object(sys, "argv", argv), \
                    patch.object(check.DOCKER, "require"), \
                    patch.object(check.DOCKER, "build", side_effect=build_error), \
                    patch.object(check.subprocess, "call", return_value=docker_status) as docker, \
                    contextlib.redirect_stdout(io.StringIO()):
                result = check.main()
            return result, docker.call_count

    def test_successful_shell_returns_success(self):
        self.assertEqual(self.run_check(), (0, 1))

    def test_failed_docker_command_returns_failure(self):
        for status in (1, 125, 126, 127):
            with self.subTest(docker_exit=status):
                self.assertEqual(self.run_check(docker_status=status), (1, 1))

    def test_no_shell_only_checks_build(self):
        self.assertEqual(self.run_check(docker_status=125, no_shell=True), (0, 0))

    def test_failed_build_does_not_start_shell(self):
        self.assertEqual(self.run_check(build_error=check.Failed("build failed")), (1, 0))


if __name__ == "__main__":
    unittest.main()
