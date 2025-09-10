#!/bin/sh
set -e

CLI_DEST="/usr/local/bin/golem-provider"
if [ -L "$CLI_DEST" ] || [ -f "$CLI_DEST" ]; then
  rm -f "$CLI_DEST"
fi

exit 0

