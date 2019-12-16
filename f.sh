# Allows fast folder switch for a given root folder.
# Manuel Martos <mmartos@degirona.info>
# Dec 16, 2019

# Include definitions
script_folder="$(dirname "$0")"
source "$script_folder/defs.sh"

# Main function
function f() {
  # If no parameters, change to root folder
  if [ $# -eq 0 ]; then
    cd $F_ROOT_FOLDER
  # If one parameter, try to find specified folder
  elif [ $# -eq 1 ]; then
    parse_result "$(folder $F_ROOT_FOLDER $1)" $1
  # If two parameters, first try to find first folder, use it as root and try to find second folder
  elif [ $# -eq 2 ]; then
    folder="$(folder $F_ROOT_FOLDER $1)"
    if [ ! -z $folder ]; then
      parse_result "$(folder $folder $2)" $2
    else
      not_found $1
    fi
  # If three parameters, imagine...
  elif [ $# -eq 3 ]; then
    folder="$(folder $F_ROOT_FOLDER $1)"
    if [ ! -z $folder ]; then
      subfolder="$(folder $folder $2)"
      if [ ! -z $subfolder ]; then
        parse_result "$(folder $subfolder $3)" $3
      else
        not_found $2
      fi
    else
      not_found $1
    fi
  fi
}

# This function receives two parameters
# $1 -> root folder
# $2 -> partial name of folder to be found
# It tries to find the first folder that matches with $2 using $1 as root folder. If there 
# isn't any match, returns empty string. Otherwise, returns the full path of the matching folder.
function folder() {
  if [ -d "$1/$2" ]; then
    echo "$1/$2"
  else
    found=false
    for i in {1..$F_MAX_DEPTH}
    do
      found_folder=`find $1 -iname "*$2*" -type d -maxdepth $i 2> /dev/null | sort | head -1`
      if [ ! -z $found_folder ]; then
        echo $found_folder
        found=true
        break
      fi
    done
    if [ $found = false ]; then
      echo ""
    fi
  fi
}

# Simply changes directory or prompts the error message.
function parse_result() {
  if [ -d "$1" ]; then
    cd $1
  else
    not_found $2
  fi
}

# Prompt error message
function not_found() {
  echo "Project '$1' not found"
}