"""Real interactive-shell regression: Ctrl-C must cancel a blocked search."""

import os
from pathlib import Path
import pty
import select
import shlex
import shutil
import signal
import tempfile
import time
import unittest


REPO = Path(__file__).resolve().parents[1]


class TerminalTests(unittest.TestCase):
    def test_ctrl_c_during_search_keeps_terminal_alive_and_pwd_unchanged(self):
        for name in ("bash", "zsh"):
            shell = shutil.which(name)
            if not shell:
                continue
            with self.subTest(shell=shell), tempfile.TemporaryDirectory() as tmp:
                home = Path(tmp)
                root = home / "projects"
                root.mkdir()
                (root / "partial-missing").mkdir()
                bin_dir = home / "bin"
                bin_dir.mkdir()
                # Deterministically simulate slow filesystem I/O at the real
                # find boundary, rather than depending on a huge directory tree.
                find = bin_dir / "find"
                find.write_text('#!/bin/sh\nprintf "%s\\0" "$F_ROOT_FOLDER/partial-missing"\nprintf "__SEARCH_RUNNING__\\n" >&2\nexec sleep 30\n')
                find.chmod(0o755)
                pid, fd = pty.fork()
                if pid == 0:
                    os.chdir(REPO)
                    env = {
                        **os.environ, "HOME": tmp, "ZDOTDIR": tmp,
                        "BASH_ENV": "/dev/null", "ENV": "/dev/null",
                        "HISTFILE": "/dev/null", "TERM": "dumb", "PS1": "f-test> ",
                        "F_ROOT_FOLDER": str(root), "F_MAX_DEPTH": "4",
                        "PATH": str(bin_dir) + os.pathsep + os.environ["PATH"],
                    }
                    args = [shell, "--noprofile", "--norc", "-i"] if name == "bash" else [shell, "-f", "-i"]
                    os.execve(shell, args, env)

                def read_until(marker):
                    output = b""
                    deadline = time.monotonic() + 5
                    while time.monotonic() < deadline:
                        if select.select([fd], [], [], 0.1)[0]:
                            try:
                                chunk = os.read(fd, 65536)
                            except OSError:
                                break
                            if not chunk:
                                break
                            output += chunk
                            if marker in output:
                                return
                    self.fail(f"terminal did not emit {marker!r}: {output!r}")

                try:
                    command = f"source {shlex.quote(str(REPO / 'f.sh'))}; printf '\\n__READY__\\n'\n"
                    os.write(fd, command.encode())
                    read_until(b"__READY__\r\n")
                    os.write(fd, b"f missing\n")
                    read_until(b"__SEARCH_RUNNING__\r\n")
                    os.write(fd, b"\x03")
                    os.write(fd, b"printf '\\n__ALIVE__:%s\\n' \"$PWD\"\n")
                    read_until(b"__ALIVE__:" + os.fsencode(REPO) + b"\r\n")
                finally:
                    # Reap even a failed/hanging test without leaving its slow
                    # search process or interactive shell running.
                    try:
                        foreground = os.tcgetpgrp(fd)
                        if foreground > 0 and foreground != os.getpgrp():
                            os.killpg(foreground, signal.SIGKILL)
                    except (OSError, ProcessLookupError):
                        pass
                    try:
                        os.kill(pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    os.close(fd)
                    os.waitpid(pid, 0)


if __name__ == "__main__":
    unittest.main()
