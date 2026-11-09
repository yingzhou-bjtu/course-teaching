#!/bin/sh
# 一行安装（macOS / Linux / WSL）：
#   sh install.sh
# 可选参数透传给 ghfast.py install，例如：
#   sh install.sh --dir "$HOME/bin"
set -eu
cd "$(dirname "$0")"

if command -v python3 >/dev/null 2>&1; then
    PY=python3
elif command -v python >/dev/null 2>&1; then
    PY=python
else
    echo "需要 Python 3.8+（未找到 python3/python）。" >&2
    echo "macOS: brew install python3    Debian/Ubuntu: sudo apt install python3" >&2
    exit 1
fi

"$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)' || {
    echo "Python 版本过低，需要 3.8+：$("$PY" -V 2>&1)" >&2
    exit 1
}

exec "$PY" ghfast.py install "$@"
