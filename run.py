#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""课程入口：不用 Jupyter 也能跑。

    python3 run.py          # 完整课程，十余秒
    python3 run.py --fast   # 两秒跑完，用来确认环境

装了 numpy 就跑完整课程；没装则自动改用纯 Python 精简版（run_lite.py），
一个第三方库都不需要。
"""

import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
NB = os.path.join(HERE, "猫狗识别.ipynb")

# 这门课的矩阵乘法都很小（一次几十乘几十），多线程反而被调度开销拖慢：
# 32 线程时每轮 40 秒，单线程 3 秒。必须在 numpy 被导入之前设置，所以放在这里。
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

# Windows 控制台默认不是 UTF-8，中文会直接抛 UnicodeEncodeError，先切一次。
for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def run_notebook(fast):
    with io.open(NB, encoding="utf-8") as f:
        notebook = json.load(f)
    cells = ["".join(c["source"]) for c in notebook["cells"] if c["cell_type"] == "code"]
    source = "\n\n".join(cells)
    if fast:
        if "FAST_DEMO = False" not in source:
            print("notebook 里的 FAST_DEMO 开关不见了，无法使用 --fast。")
            return 2
        source = source.replace("FAST_DEMO = False", "FAST_DEMO = True")

    print("=" * 60)
    print("猫狗识别 · 完整课程（无需 Jupyter）")
    print("=" * 60)
    namespace = {"__name__": "__main__"}
    exec(compile(source, NB, "exec"), namespace)
    acc = namespace.get("val_acc")
    figures = os.path.join(HERE, "figures")
    if os.path.isdir(figures) and os.listdir(figures):
        print("教学图已存到 figures/ 目录（共 %d 张）" % len(os.listdir(figures)))
    print("=" * 60)
    print("运行结束，验证集准确率 %.4f" % acc if acc is not None else "运行结束")
    print("=" * 60)
    return 0


def main():
    fast = "--fast" in sys.argv[1:]
    try:
        import numpy  # noqa: F401
    except ImportError:
        print("没有安装 numpy，改用纯 Python 精简版，不需要安装任何东西。")
        print("想跑完整课程，装一次即可：")
        print("  python3 -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple numpy")
        print()
        sys.argv = [sys.argv[0], "--fast"] if fast else [sys.argv[0]]
        import run_lite
        return run_lite.main()

    if not os.path.exists(NB):
        print("找不到 猫狗识别.ipynb，请确认当前目录是解压后的文件夹。")
        return 2
    return run_notebook(fast)


if __name__ == "__main__":
    raise SystemExit(main())
