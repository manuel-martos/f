#!/usr/bin/env bash
# User-local installation; no sudo or runtime package manager required.
set -euo pipefail

usage() {
  printf '%s\n' \
    'Usage: bash install.sh [--shell bash|zsh] [--prefix DIR] [--rc FILE] [--no-rc]' \
    '' \
    '  --shell   Shell to configure (default: $SHELL)' \
    '  --prefix  Install directory (default: ${XDG_DATA_HOME:-$HOME/.local/share}/f)' \
    '  --rc      Startup file (default: .zshrc, or .bashrc/.bash_profile on macOS)' \
    '  --no-rc   Install files only; print the line to source manually' \
    '  --help    Show this help'
}

die() { printf 'f install: %s\n' "$*" >&2; exit 1; }

shell_name=${SHELL-}
shell_name=${shell_name##*/}
prefix=${XDG_DATA_HOME:-$HOME/.local/share}/f
rc_file=''
no_rc=0
tmp=''
trap '[ -z "$tmp" ] || rm -f -- "$tmp"' EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
trap 'exit 129' HUP

while [ "$#" -gt 0 ]; do
  case "$1" in
    --shell|--prefix|--rc)
      [ "$#" -ge 2 ] && [ -n "$2" ] || die "$1 requires a value"
      case "$1" in
        --shell) shell_name=$2 ;;
        --prefix) prefix=$2 ;;
        --rc) rc_file=$2 ;;
      esac
      shift 2 ;;
    --no-rc) no_rc=1; shift ;;
    --help|-h) usage; exit 0 ;;
    *) die "unknown option: $1 (see --help)" ;;
  esac
done
case "$shell_name" in
  bash|zsh) ;;
  *) die 'choose a supported shell with --shell bash or --shell zsh' ;;
esac
[ "$no_rc" -eq 0 ] || [ -z "$rc_file" ] || die '--rc and --no-rc cannot be combined'
case "$prefix$rc_file" in
  *$'\n'*|*$'\r'*) die 'installation and startup paths must not contain newlines' ;;
esac

source_dir=$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
[ -f "$source_dir/f.sh" ] && [ -f "$source_dir/defs.sh" ] || die 'run this installer from a complete checkout'
mkdir -p -- "$prefix"
prefix=$(CDPATH= cd -- "$prefix" && pwd -P)
if [ "$prefix" != "$source_dir" ]; then
  command install -m 644 "$source_dir/f.sh" "$source_dir/defs.sh" "$prefix/"
fi
# printf %q produces a source line understood by both Bash and Zsh, including
# paths with spaces, quotes, or shell metacharacters. Never eval path input.
printf -v quoted_script '%q' "$prefix/f.sh"
source_line="[ ! -r $quoted_script ] || source $quoted_script"

if [ "$no_rc" -eq 0 ]; then
  if [ -z "$rc_file" ]; then
    if [ "$shell_name" = zsh ]; then
      rc_file=${ZDOTDIR:-$HOME}/.zshrc
    elif [ "$(uname -s)" = Darwin ]; then
      # Bash login shells read the first existing file in this order.
      if [ -f "$HOME/.bash_profile" ]; then rc_file=$HOME/.bash_profile
      elif [ -f "$HOME/.bash_login" ]; then rc_file=$HOME/.bash_login
      elif [ -f "$HOME/.profile" ]; then rc_file=$HOME/.profile
      else rc_file=$HOME/.bash_profile
      fi
    else
      rc_file=$HOME/.bashrc
    fi
  fi

  # Update a symlink's referent, not the symlink (common in dotfile repositories).
  links=0
  while [ -L "$rc_file" ]; do
    links=$((links + 1))
    [ "$links" -le 40 ] || die 'startup file has a symlink loop'
    target=$(readlink "$rc_file")
    case "$target" in
      /*) rc_file=$target ;;
      *) rc_file=$(dirname -- "$rc_file")/$target ;;
    esac
  done
  [ ! -e "$rc_file" ] || [ -f "$rc_file" ] || die "not a regular startup file: $rc_file"
  mkdir -p -- "$(dirname -- "$rc_file")"
  rc_file=$(CDPATH= cd -- "$(dirname -- "$rc_file")" && pwd -P)/$(basename -- "$rc_file")
  start='# >>> f shell navigation >>>'
  end='# <<< f shell navigation <<<'
  tmp=$(mktemp "$rc_file.f-install.XXXXXX")
  if [ -f "$rc_file" ]; then
    cp -p -- "$rc_file" "$tmp"
    # Remove old managed blocks, but refuse malformed markers rather than
    # accidentally deleting unrelated startup commands.
    awk -v start="$start" -v end="$end" '
      $0 == start { if (inside) exit 1; inside = 1; next }
      $0 == end { if (!inside) exit 1; inside = 0; next }
      !inside { print }
      END { if (inside) exit 1 }
    ' "$rc_file" > "$tmp" || die "malformed f block in $rc_file; left unchanged"
  fi
  printf '%s\n' "$start" "$source_line" "$end" >> "$tmp"
  if [ -f "$rc_file" ] && cmp -s -- "$rc_file" "$tmp"; then
    rm -f -- "$tmp"
  else
    if [ -f "$rc_file" ]; then
      backup=$(mktemp "$rc_file.f-backup.XXXXXX")
      cp -p -- "$rc_file" "$backup"
      printf 'Backup: %s\n' "$backup"
    fi
    mv -f -- "$tmp" "$rc_file"
  fi
  tmp=''
  printf 'Configured: %s\n' "$rc_file"
fi
printf 'Installed: %s\n\nRun this in your current %s session (or open a new terminal):\n%s\n' "$prefix" "$shell_name" "$source_line"
