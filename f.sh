# Source this file from Bash or Zsh; f must run in the calling shell to change PWD.
# Manuel Martos <mmartos@degirona.info>

if [ -n "${ZSH_VERSION-}" ]; then
  source "${${(%):-%x}:A:h}/defs.sh"
elif [ -n "${BASH_VERSION-}" ]; then
  source "$(command dirname -- "${BASH_SOURCE[0]}")/defs.sh"
else
  printf 'f: only Bash and Zsh are supported\n' >&2
  return 1
fi

f() {
  # Zsh options such as SH_WORD_SPLIT must not change our path handling.
  if [ -n "${ZSH_VERSION-}" ]; then emulate -L zsh; fi
  local current_root term depth
  local CDPATH=''

  if [ -z "${F_ROOT_FOLDER-}" ] || [ ! -d "$F_ROOT_FOLDER" ]; then
    printf 'f: F_ROOT_FOLDER is not a directory: %s\n' "${F_ROOT_FOLDER-}" >&2
    return 1
  fi
  case "${F_MAX_DEPTH-}" in
    ''|*[!0-9]*)
      printf 'f: F_MAX_DEPTH must be an integer between 1 and 64\n' >&2
      return 1 ;;
  esac
  if [ "${#F_MAX_DEPTH}" -gt 2 ]; then
    printf 'f: F_MAX_DEPTH must be an integer between 1 and 64\n' >&2
    return 1
  fi
  depth=$((10#$F_MAX_DEPTH))
  if [ "$depth" -lt 1 ] || [ "$depth" -gt 64 ]; then
    printf 'f: F_MAX_DEPTH must be an integer between 1 and 64\n' >&2
    return 1
  fi

  # Resolve relative roots without moving the caller or running Zsh cd hooks.
  # A trailing slash preserves names ending in newlines in command substitution.
  current_root=$(
    if [ -n "${ZSH_VERSION-}" ]; then
      builtin cd -q -- "$F_ROOT_FOLDER"
    else
      builtin cd -- "$F_ROOT_FOLDER"
    fi && printf '%s/\n' "$PWD"
  ) || return 1
  for term in "$@"; do
    if [ -z "$term" ]; then
      printf 'f: folder queries must not be empty\n' >&2
      return 1
    fi
    current_root=$(__f_find_folder "${current_root%/}" "$term" "$depth") || return 1
  done
  builtin cd -- "$current_root"
}

# One bounded traversal per query; no sorting/buffering of the entire tree.
# Run in a subshell to isolate pipefail and locale from the caller.
__f_find_folder() (
  if [ -n "${ZSH_VERSION-}" ]; then emulate -L zsh; fi
  set -o pipefail
  export LC_ALL=C
  local root="$1" term="$2" max_depth="$3" pattern

  if [ -d "$root/$term" ]; then
    printf '%s/\n' "$root/$term"
    return 0
  fi

  # find uses glob syntax. Queries are literal, case-insensitive substrings.
  pattern=${term//\\/\\\\}
  pattern=${pattern//\*/\\*}
  pattern=${pattern//\?/\\?}
  pattern=${pattern//\[/\\[}
  pattern=${pattern//\]/\\]}

  # A trailing slash follows an explicitly chosen symlink root, but -P still
  # prevents following directory symlinks encountered during the traversal.
  command find -P "$root/" -mindepth 1 -maxdepth "$max_depth" \
    -type d -iname "*$pattern*" -print0 | (
    local candidate relative candidate_depth best='' best_depth=65
    while IFS= read -r -d '' candidate; do
      relative=${candidate#"$root"/}
      candidate_depth=1
      while [[ "$relative" == */* ]]; do
        relative=${relative#*/}
        candidate_depth=$((candidate_depth + 1))
      done
      if [ "$candidate_depth" -lt "$best_depth" ] || {
        [ "$candidate_depth" -eq "$best_depth" ] && [[ "$candidate" < "$best" ]]
      }; then
        best=$candidate
        best_depth=$candidate_depth
      fi
    done
    if [ -z "$best" ]; then
      printf "f: folder '%s' not found under '%s' (depth %s)\n" "$term" "$root" "$max_depth" >&2
      return 1
    fi
    printf '%s/\n' "$best"
  )
)
