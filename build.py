#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""跨平台打包：把 ghfast.py 打成单文件 zipapp。

    python3 build.py        ->  dist/ghfast.pyz

产物只依赖 Python 3.8+ 解释器（Windows / macOS / Linux 均可直接运行），
因为项目本身没有任何第三方依赖，所以「打包」= 打一个文件。
"""

import os
import shutil
import subprocess
import sys
import tempfile
import zipapp

ROOT = os.path.dirname(os.path.abspath(__file__))


def main() -> int:
    src = os.path.join(ROOT, "ghfast.py")
    with open(src, "rb") as f:
        compile(f.read(), src, "exec")  # 语法检查，失败会直接抛异常

    out_dir = os.path.join(ROOT, "dist")
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, "ghfast.pyz")

    with tempfile.TemporaryDirectory() as stage:
        app = os.path.join(stage, "app")
        os.makedirs(app)
        shutil.copyfile(src, os.path.join(app, "__main__.py"))
        zipapp.create_archive(app, target=out,
                              interpreter="/usr/bin/env python3", compressed=True)

    try:
        os.chmod(out, 0o755)
    except OSError:
        pass

    print("built: %s (%.1f KiB)" % (os.path.relpath(out, ROOT), os.path.getsize(out) / 1024.0))
    r = subprocess.run([sys.executable, out, "--version"], capture_output=True, text=True)
    print((r.stdout or r.stderr).strip())
    return 0 if r.returncode == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
