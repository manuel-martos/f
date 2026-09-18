"""Integration tests; no packages required. Run: python3 -m unittest discover -s tests -v."""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[1]
SHELLS = [shutil.which(name) for name in ("bash", "zsh") if shutil.which(name)]


class NavigationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="f tests ")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "projects"
        self.root.mkdir()
        self.env = {
            **os.environ, "HOME": self.tmp.name, "ZDOTDIR": self.tmp.name,
            "BASH_ENV": "/dev/null", "ENV": "/dev/null",
            "F_ROOT_FOLDER": str(self.root), "F_MAX_DEPTH": "4",
        }

    def folder(self, name):
        path = self.root / name
        path.mkdir(parents=True, exist_ok=True)
        return path

    def run_shell(self, shell, code, *args, env=None):
        # Give old versions a valid $0 so their source-path bug doesn't hide others.
        return subprocess.run(
            [shell, "-c", 'source "$1/f.sh"; ' + code, str(REPO / "f.sh"), str(REPO), *map(str, args)],
            cwd=REPO,
            env={**self.env, **(env or {})},
            capture_output=True,
            timeout=5,
        )

    def assert_destination(self, code, expected, *args, env=None):
        for shell in SHELLS:
            with self.subTest(shell=shell):
                result = self.run_shell(shell, code + ' || exit; printf "%s\\0" "$PWD"', *args, env=env)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stderr, b"")
                self.assertEqual(result.stdout, os.fsencode(expected) + b"\0")

    def test_failure_returns_without_terminating_shell_or_changing_directory(self):
        for shell in SHELLS:
            with self.subTest(shell=shell):
                result = self.run_shell(shell, 'F_ROOT_FOLDER="$2"; if f absent; then exit 90; fi; printf "alive:%s" "$PWD"', self.root)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, b"alive:" + os.fsencode(REPO))
                self.assertIn(b"not found", result.stderr)

    def test_source_from_another_directory_preserves_configuration(self):
        for shell in SHELLS:
            with self.subTest(shell=shell):
                result = subprocess.run(
                    [shell, "-c", 'source "$1/f.sh"; f; printf "%s\\0" "$PWD"', shell, str(REPO)],
                    cwd=self.tmp.name,
                    env=self.env,
                    capture_output=True, timeout=5,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stderr, b"")
                self.assertEqual(result.stdout, os.fsencode(self.root) + b"\0")

    def test_no_arguments_goes_to_root(self):
        self.assert_destination("f", self.root)

    def test_nested_case_insensitive_substring(self):
        target = self.folder("group/MyPROJECT")
        self.assert_destination("f project", target)

    def test_sequential_arguments(self):
        target = self.folder("company/backend-service/source")
        self.assert_destination("f company backend source", target)

    def test_later_failure_is_atomic(self):
        self.folder("company")
        for shell in SHELLS:
            with self.subTest(shell=shell):
                result = self.run_shell(shell, 'if f company absent; then exit 90; fi; printf "%s" "$PWD"')
                self.assertEqual(result.returncode, 0)
                self.assertEqual(result.stdout, os.fsencode(REPO))

    def test_exact_child_wins_over_partial_match(self):
        self.folder("aaa-project")
        target = self.folder("project")
        self.assert_destination("f project", target)

    def test_nearest_match_then_alphabetical_tie_break(self):
        self.folder("aaa/deep-match")
        self.folder("z-match")
        target = self.folder("b-match")
        self.assert_destination("f match", target)

    def test_spaces_tabs_newlines_and_globs_are_literal(self):
        for name in ("two words", "tab\there", "new\nline\n", "star*here", "question?here", "bracket[here]", "back\\slash", "-leading", "quote'$(false)"):
            target = self.folder("parent/" + name)
            with self.subTest(name=name):
                self.assert_destination('f "$2"', target, name)

    def test_pattern_characters_do_not_match_arbitrary_names(self):
        self.folder("anything")
        for shell in SHELLS:
            with self.subTest(shell=shell):
                result = self.run_shell(shell, 'if f "*"; then exit 90; fi; printf alive')
                self.assertEqual(result.returncode, 0)
                self.assertEqual(result.stdout, b"alive")

    def test_depth_limit(self):
        self.folder("one/two/needle")
        for shell in SHELLS:
            with self.subTest(shell=shell):
                result = self.run_shell(shell, 'if f needle; then exit 90; fi; printf alive', env={"F_MAX_DEPTH": "2"})
                self.assertEqual(result.returncode, 0)
                self.assertEqual(result.stdout, b"alive")
        self.assert_destination("f needle", self.root / "one/two/needle", env={"F_MAX_DEPTH": "3"})

    def test_invalid_configuration_and_empty_query(self):
        for shell in SHELLS:
            for setting in ('F_ROOT_FOLDER=""', 'F_ROOT_FOLDER=/nonexistent-f-test', 'F_MAX_DEPTH=0', 'F_MAX_DEPTH=-1', 'F_MAX_DEPTH=abc', 'F_MAX_DEPTH=999999999999999999999'):
                with self.subTest(shell=shell, setting=setting):
                    result = self.run_shell(shell, setting + '; if f; then exit 90; fi; printf alive')
                    self.assertEqual(result.returncode, 0)
                    self.assertEqual(result.stdout, b"alive")
                    self.assertTrue(result.stderr)
            result = self.run_shell(shell, 'if f ""; then exit 90; fi; printf alive')
            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stdout, b"alive")

    def test_symlink_cycles_not_followed_but_exact_links_work(self):
        self.folder("group")
        (self.root / "group/loop").symlink_to(self.root, target_is_directory=True)
        self.assert_destination("f group loop", self.root / "group/loop")
        for shell in SHELLS:
            result = self.run_shell(shell, 'if f absent; then exit 90; fi; printf alive')
            self.assertEqual(result.stdout, b"alive")

    def test_symlink_root_and_search_inside_exact_symlink(self):
        target = self.folder("real/deep/my-project")
        link = self.root / "link"
        link.symlink_to(self.root / "real", target_is_directory=True)
        self.assert_destination("f project", link / "deep/my-project", env={"F_ROOT_FOLDER": str(link)})
        self.assert_destination("f link project", link / "deep/my-project")
        self.assertTrue(target.is_dir())

    def test_cdpath_and_user_cd_function_do_not_interfere(self):
        target = self.folder("project")
        self.assert_destination('CDPATH=/tmp; cd() { printf "custom cd"; }; f project', target)

    @unittest.skipUnless(shutil.which("zsh"), "Zsh is not installed")
    def test_zsh_directory_hooks_run_only_for_the_final_jump(self):
        target = self.folder("my-project")
        result = self.run_shell(shutil.which("zsh"), 'chpwd() { printf "hook:%s\\n" "$PWD"; }; f project || exit; printf "pwd:%s" "$PWD"')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, os.fsencode(f"hook:{target}\npwd:{target}"))
        self.assertEqual(result.stderr, b"")

    def test_does_not_overwrite_caller_variables_or_options(self):
        self.folder("my-project")
        for shell in SHELLS:
            with self.subTest(shell=shell):
                result = self.run_shell(shell, 'current_root=keep; found_folder=keep; i=keep; found=keep; before=$(set +o); f project || exit; after=$(set +o); [ "$before" = "$after" ] || exit 91; printf "%s" "$current_root:$found_folder:$i:$found"')
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, b"keep:keep:keep:keep")

    def test_search_errors_do_not_navigate_to_partial_results(self):
        target = self.folder("partial-match")
        bin_dir = Path(self.tmp.name) / "bin"
        bin_dir.mkdir()
        fake_find = bin_dir / "find"
        fake_find.write_text('#!/bin/sh\nprintf "%s\\0" "$FAKE_MATCH"\nprintf "find failed\\n" >&2\nexit 1\n')
        fake_find.chmod(0o755)
        for shell in SHELLS:
            with self.subTest(shell=shell):
                result = self.run_shell(shell, 'if f match; then exit 90; fi; printf "%s" "$PWD"', env={"PATH": str(bin_dir) + os.pathsep + os.environ["PATH"], "FAKE_MATCH": str(target)})
                self.assertEqual(result.returncode, 0)
                self.assertEqual(result.stdout, os.fsencode(REPO))
                self.assertIn(b"find failed", result.stderr)


if __name__ == "__main__":
    unittest.main()
