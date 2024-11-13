#!/usr/bin/env bash
workspace="b2m"

# Shell Workspace File
# This is designed to be used with github.com/nepthar/ws.sh for "magic",
# it can be sourced from bash, or it can be executed directly.


b2m.run() {
  ./.venv/bin/python main.py "$@"
}

# I've never run this, it's just notes for what I did.
b2m.bootstrap() {
  # Make sure venv is installed
  sudo apt isntall python3.11-venv

  # make a virutal evn in the current folder
  python3 -m venv ./.venv

  # enter it
  source .venv/bin/activate

  # install all requirements
  pip install -r requirements.txt
}

# Run a command if this is being executed instead of sourced.
if [[ "$0" == *workspace.sh ]]; then
  funcname="${workspace}.${1}"
  shift 1
  cd $(dirname $0)
  $funcname "$@"
fi
