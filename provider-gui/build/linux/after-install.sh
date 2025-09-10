#!/bin/sh
set -e

APP_NAME="Golem Provider"
APP_DIR="/opt/$APP_NAME"
CLI_SRC="$APP_DIR/resources/cli/linux/golem-provider"
CLI_DEST="/usr/local/bin/golem-provider"

if [ -x "$CLI_SRC" ]; then
  ln -sf "$CLI_SRC" "$CLI_DEST"
  chmod +x "$CLI_SRC"
fi

exit 0

