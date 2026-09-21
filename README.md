# f — Fancy F Function

A small Bash/Zsh function for jumping to folders under a configured root. Type
partial folder names instead of full paths, and chain queries to descend through
your projects. No directory-history database, fuzzy-finder dependency, or daemon.

Given this tree:

```text
~/Development/
└── acme/
    ├── api-service/
    │   └── src/
    └── web-client/
```

```sh
f                 # ~/Development
f api             # ~/Development/acme/api-service
f acme web        # ~/Development/acme/web-client
f acme api src    # ~/Development/acme/api-service/src
f "my project"    # quote names containing spaces or shell metacharacters
```

## Requirements

- **Bash 3.2+ or Zsh 5+**, on macOS or Linux.
- Standard system utilities, including BSD/GNU `find` with `-maxdepth`, `-iname`,
  and `-print0` (provided by macOS and typical Linux distributions).
- Bash to run the installer. Python 3 is needed **only for tests**.

`f.sh` must be **sourced**, not executed: only a shell function can change the
current terminal's working directory. Fish and plain POSIX `sh` are not supported.

## Install

```sh
git clone https://github.com/manuel-martos/f.git
cd f
bash install.sh --shell zsh    # use --shell bash for Bash
```

The installer:

- Copies `f.sh` and `defs.sh` to `${XDG_DATA_HOME:-$HOME/.local/share}/f`, without sudo.
- Adds one managed block to your shell startup file; rerunning updates it instead
  of duplicating it.
- Preserves unrelated startup commands and existing permissions, follows startup
  file symlinks, and creates a uniquely named `.f-backup.*` copy before changes.
- Prints the source command to activate `f` in the current terminal. Alternatively,
  open a new terminal.

Zsh uses `${ZDOTDIR:-$HOME}/.zshrc`. Bash uses `~/.bashrc` on Linux; on macOS it
uses the first existing login file (`.bash_profile`, `.bash_login`, `.profile`),
or creates `.bash_profile`. For a different shell setup, choose the startup file
explicitly:

```sh
bash install.sh --shell bash --rc "$HOME/.bashrc"
bash install.sh --shell zsh --prefix "$HOME/.local/share/f" --no-rc
bash install.sh --help
```

`--no-rc` installs the files without editing any startup file. Bash login shells
on Linux must source `.bashrc` from their login file, or use `--rc` to target that
file directly.

### Manual installation

Keep the checkout anywhere and add this to `.bashrc` or `.zshrc`:

```sh
source "/absolute/path/to/f/f.sh"
```

Keep `defs.sh` beside `f.sh`. No executable or `PATH` changes are needed.

## Configuration

Set these in your shell startup file, preferably **before** the source line or
installer-managed block:

```sh
F_ROOT_FOLDER="$HOME/Development"  # must exist; f does not create it
F_MAX_DEPTH=4                       # recursive search depth per query (1–64)
```

Existing values are preserved when sourcing again. You can also change them in
the current session. Do not edit the installed `defs.sh`: upgrades replace it.
If you customized `defs.sh` in an older checkout, move those settings into your
startup file before upgrading.

## Matching and safety

1. With no arguments, go to `F_ROOT_FOLDER`.
2. For each argument, prefer an existing exact path relative to the current search
   root. Explicit paths such as `f acme/api-service` bypass the recursive depth limit.
3. Otherwise, search directory **names** for a literal, case-insensitive substring,
   up to `F_MAX_DEPTH` levels below that root. Case folding uses the C locale (ASCII).
4. Prefer the shallowest match; break ties by full-path byte order. Each next
   argument starts searching inside the previous match. This is substring matching,
   not typo-tolerant fuzzy matching.
5. Change directory only after **all** arguments resolve successfully.

Failures return a nonzero status and print diagnostics to stderr; they never call
`exit` or leave you halfway through a multi-step jump. Filenames containing spaces,
newlines, wildcard characters, or leading dashes are handled literally when quoted.
Shell variables and options are not overwritten, apart from the normal effects of
`cd` (`PWD`/`OLDPWD`). In scripts using `set -e`, handle failure explicitly, e.g.
`if f missing; then ...; fi`, as with any command returning nonzero.

Searches use one depth-bounded traversal per query, without sorting the whole tree.
Hidden directories are included. Symlinks encountered during recursive searches
are not followed, preventing cycles; an explicitly selected symlink directory is
allowed. Explicit `..` paths can leave the configured root: this is a navigation
tool, not a sandbox.

Very wide trees, large depth settings, or slow/network filesystems can still take
time: a depth bound is not a time limit. Use a narrower root or smaller depth, or
press **Ctrl-C** to cancel a search. Filesystem errors fail the lookup rather than
silently selecting an incomplete result.

## Update / uninstall

To update, pull changes in your checkout and rerun the installer with the same
options. Configuration in your startup file is retained.

To uninstall, remove the block between `# >>> f shell navigation >>>` and
`# <<< f shell navigation <<<` from your startup file (or your manual source line).
Delete `f.sh` and `defs.sh` from the installation directory if no longer needed.
Open a new terminal, or run `unset -f f __f_find_folder` in the current session.

## Similar tools

Yes—directory jumping is a well-established category. These descriptions are
based on the projects' own documentation:

| Tool | Approach / difference from `f` |
| --- | --- |
| [zoxide](https://github.com/ajeetdsouza/zoxide#readme) | Remembers frequently used directories and ranks matching destinations. A good general-purpose choice if you want history-based jumping. |
| [autojump](https://github.com/wting/autojump#readme) | Maintains a database of visited directories; destinations must have been visited first. |
| [z](https://github.com/rupa/z#readme) | Shell-based navigation ranked by “frecency” (frequency and recency), with regex matching. |
| [fzf](https://github.com/junegunn/fzf#key-bindings-for-command-line) | General interactive fuzzy finder; its **Alt-C** shell binding selects a directory and changes into it. |

`f` is useful when you want a tiny, deterministic, root-scoped search that works
on directories you have **never visited**, without maintaining history. Choose
zoxide for learned shortcuts, or fzf if you prefer choosing matches interactively.

## Development

```sh
python3 -m unittest discover -s tests -v
```

Tests exercise each available shell (install both Bash and Zsh for full coverage),
including real pseudo-terminal Ctrl-C handling. Installer tests use temporary homes
and never edit your actual startup files. CI runs the suite on macOS and Linux.
