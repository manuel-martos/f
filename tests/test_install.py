"""Exercise the installer only against temporary homes and startup files."""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[1]


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="f install ")
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.prefix = self.home / "data dir's $literal/f"
        self.rc = self.home / "config dir/shell rc"
        self.env = {
            **os.environ, "HOME": str(self.home), "SHELL": "/bin/zsh",
            "BASH_ENV": "/dev/null", "ENV": "/dev/null",
            "XDG_DATA_HOME": str(self.home / "xdg"), "ZDOTDIR": str(self.home / "zsh"),
        }

    def install(self, *args, defaults=False):
        options = [] if defaults else ["--prefix", str(self.prefix), "--rc", str(self.rc)]
        return subprocess.run(
            ["bash", str(REPO / "install.sh"), *options, *args],
            cwd=self.home, env=self.env, capture_output=True, timeout=5,
        )

    def test_install_is_idempotent_and_preserves_user_configuration(self):
        self.rc.parent.mkdir()
        root = self.home / "my projects"
        root.mkdir()
        original = f'F_ROOT_FOLDER="{root}"\nF_MAX_DEPTH=2\n# user configuration\n'
        self.rc.write_text(original)
        self.rc.chmod(0o640)
        for _ in range(2):
            result = self.install()
            self.assertEqual(result.returncode, 0, result.stderr)
        contents = self.rc.read_text()
        self.assertTrue(contents.startswith(original))
        self.assertEqual(contents.count("# >>> f shell navigation >>>"), 1)
        self.assertEqual(self.rc.stat().st_mode & 0o777, 0o640)
        backups = list(self.rc.parent.glob(self.rc.name + ".f-backup.*"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_text(), original)
        for name in ("f.sh", "defs.sh"):
            self.assertEqual((self.prefix / name).read_bytes(), (REPO / name).read_bytes())
        for name in ("bash", "zsh"):
            shell = shutil.which(name)
            if not shell:
                continue
            with self.subTest(shell=shell):
                run = subprocess.run(
                    [shell, "-c", 'source "$1"; f || exit; printf "%s:%s" "$PWD" "$F_MAX_DEPTH"', shell, str(self.rc)],
                    cwd=self.home, env=self.env, capture_output=True, timeout=5,
                )
                self.assertEqual(run.returncode, 0, run.stderr)
                self.assertEqual(run.stdout, os.fsencode(root) + b":2")
                self.assertEqual(run.stderr, b"")

    def test_reinstall_changes_only_managed_block(self):
        self.assertEqual(self.install().returncode, 0)
        with self.rc.open("a") as stream:
            stream.write("# keep after block\n")
        new_prefix = self.home / "new prefix"
        result = self.install("--prefix", str(new_prefix))
        self.assertEqual(result.returncode, 0, result.stderr)
        contents = self.rc.read_text()
        self.assertEqual(contents.count("# >>> f shell navigation >>>"), 1)
        self.assertIn("# keep after block", contents)
        self.assertNotIn("literal", contents)

    def test_default_xdg_and_zdotdir_locations(self):
        result = self.install(defaults=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.home / "xdg/f/f.sh").is_file())
        self.assertTrue((self.home / "zsh/.zshrc").is_file())

    def test_no_rc_prints_source_line_without_editing_startup_files(self):
        result = self.install("--no-rc", "--prefix", str(self.prefix), defaults=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.rc.exists())
        self.assertFalse((self.home / "zsh").exists())
        self.assertIn(b"source ", result.stdout)
        self.assertTrue((self.prefix / "f.sh").exists())

    def test_existing_symlink_and_permissions_are_preserved(self):
        self.rc.parent.mkdir()
        target = self.rc.parent / "real rc"
        target.write_text("# original\n")
        target.chmod(0o640)
        self.rc.symlink_to(target.name)
        result = self.install()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(self.rc.is_symlink())
        self.assertEqual(target.stat().st_mode & 0o777, 0o640)
        self.assertIn("# original", target.read_text())
        self.assertIn("source ", target.read_text())

    def test_malformed_blocks_leave_startup_file_unchanged(self):
        self.rc.parent.mkdir()
        for original in (
            "# original\n# >>> f shell navigation >>>\nkeep this\n",
            "# <<< f shell navigation <<<\n# original\n",
            "# >>> f shell navigation >>>\n# >>> f shell navigation >>>\n# <<< f shell navigation <<<\n",
        ):
            with self.subTest(original=original):
                self.rc.write_text(original)
                result = self.install()
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(self.rc.read_text(), original)
                self.assertIn(b"malformed", result.stderr)
                self.assertEqual(list(self.rc.parent.glob("*.f-install.*")), [])

    def test_invalid_options(self):
        for options in (("--shell", "fish"), ("--wat",), ("--prefix",), ("--rc", ""), ("--no-rc",)):
            with self.subTest(options=options):
                result = self.install(*options)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(self.rc.exists())

    def test_help_does_not_install(self):
        result = self.install("--help", defaults=True)
        self.assertEqual(result.returncode, 0)
        self.assertIn(b"Usage:", result.stdout)
        self.assertFalse((self.home / "xdg").exists())


if __name__ == "__main__":
    unittest.main()
