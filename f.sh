# Allows fast folder switch for a given root folder.
# Manuel Martos <mmartos@degirona.info>
# Dec 16, 2019

# Include definitions
script_folder="$(dirname "$0")"
source "$script_folder/defs.sh"

# Main function
function f() {
  current_root=$F_ROOT_FOLDER
  while [ $# -ne 0 ]; do
    current_root="$(folder $current_root $1)"
    if [ -z $current_root ]; then
      not_found $1
      exit -1
    fi
    shift
  done
  cd $current_root
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

# Prompt error message
function not_found() {
  echo "Project '$1' not found"
}