#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""不用 Jupyter，直接运行 猫狗识别.ipynb。

    python3 run.py          # 正常跑，十几秒
    python3 run.py --fast   # 两秒跑完，用来确认环境

只依赖 numpy。缺 numpy 时会打印安装办法，不会报一屏看不懂的错误。
"""

import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
NB = os.path.join(HERE, "猫狗识别.ipynb")

HELP = """这台电脑上没有找到 numpy，课程跑不起来。
numpy 是唯一必需的库，按你的情况选一条命令执行：

（1）电脑能上外网，用国内镜像安装，通常几十秒
    python3 -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple numpy

（2）已经有 vendor 目录（里面是 .whl 文件），不用联网
    python3 -m pip install --no-index --find-links vendor numpy

（3）服务器完全不能联网，也没有 vendor 目录
    先在一台能上网的电脑上执行下面这条，把生成的 vendor 目录拷到服务器
    python3 -m pip download numpy -d vendor --only-binary=:all: -i https://pypi.tuna.tsinghua.edu.cn/simple
    然后在服务器上执行第（2）条。

装完用这条命令确认：
    python3 -c "import numpy; print(numpy.__version__)"
"""


def main():
    fast = "--fast" in sys.argv[1:]
    try:
        import numpy  # noqa: F401
    except ImportError:
        print(HELP)
        return 2

    if not os.path.exists(NB):
        print("找不到 猫狗识别.ipynb，请确认当前目录是解压后的文件夹。")
        return 2

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
    print("猫狗识别课程，直接运行（不需要 Jupyter）")
    print("=" * 60)
    namespace = {"__name__": "__main__"}
    exec(compile(source, NB, "exec"), namespace)

    acc = namespace.get("val_acc")
    print("=" * 60)
    if acc is not None:
        print("运行结束，验证集准确率 %.4f" % acc)
    else:
        print("运行结束")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
