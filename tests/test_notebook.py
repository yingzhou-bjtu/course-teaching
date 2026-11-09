# -*- coding: utf-8 -*-
"""把《猫狗识别.ipynb》真的执行一遍（FAST 模式），保证课程不会腐烂。

    python -m unittest tests.test_notebook -v

不依赖 Jupyter：抽出全部 code cell，替换 FAST_DEMO 开关后直接 exec。
"""

import contextlib
import io
import json
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NB = os.path.join(ROOT, "猫狗识别.ipynb")


class NotebookRun(unittest.TestCase):
    ns = {}
    out = ""
    source = ""

    @classmethod
    def setUpClass(cls):
        try:
            import numpy  # noqa: F401
        except ImportError:
            raise unittest.SkipTest("需要 numpy：pip install numpy")
        if not os.path.exists(NB):
            raise unittest.SkipTest("找不到 notebook：" + NB)

        with open(NB, encoding="utf-8") as f:
            nb = json.load(f)
        cells = ["".join(c["source"]) for c in nb["cells"] if c["cell_type"] == "code"]
        src = "\n\n".join(cells)
        if "FAST_DEMO = False" not in src:
            raise AssertionError("notebook 里找不到 FAST_DEMO 开关，测试无法降规模")
        cls.source = src
        src = src.replace("FAST_DEMO = False", "FAST_DEMO = True")

        cls.ns = {"__name__": "__main__"}
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            exec(compile(src, NB, "exec"), cls.ns)
        cls.out = buf.getvalue()

        try:
            import matplotlib.pyplot as plt

            plt.close("all")
        except Exception:
            pass

    def test_notebook_runs_end_to_end(self):
        self.assertIn("总训练时间", self.out)
        self.assertIn("混淆矩阵", self.out)

    def test_accuracy_above_chance(self):
        # 合成数据 1 个 epoch，应明显高于 0.5 的随机水平
        self.assertGreater(self.ns["val_acc"], 0.6)

    def test_shapes(self):
        self.assertEqual(self.ns["Xtr"].shape[1:], (3, 32, 32))
        self.assertEqual(self.ns["Xva"].shape[1:], (3, 32, 32))
        logits = self.ns["model"].forward(self.ns["Xtr"][:2])
        self.assertEqual(logits.shape, (2, 2))

    def test_gradient_check_passes(self):
        self.assertIn("最大相对误差", self.out)
        self.assertIn("误差与解析梯度同量级", self.out)

    def test_sample_images_come_from_disk(self):
        # 仓库预置了 data/sample，装了 Pillow 就必须从磁盘读回来
        try:
            import PIL  # noqa: F401
        except ImportError:
            raise unittest.SkipTest("没装 Pillow，样板图走程序现画的分支")
        self.assertIn("data/sample（从磁盘读取）", self.out)
        self.assertEqual(self.ns["X_snap"].shape[1:], (3, 96, 96))

    def test_figures_written(self):
        try:
            import matplotlib  # noqa: F401
        except ImportError:
            raise unittest.SkipTest("没装 matplotlib，不产出教学图")
        figures = os.path.join(ROOT, "figures")
        for name in ("01_samples", "02_conv_kernels", "03_training_curves",
                     "04_confusion_matrix", "05_predictions"):
            path = os.path.join(figures, name + ".png")
            self.assertTrue(os.path.exists(path) and os.path.getsize(path) > 1000, path)

    def test_offline_and_dependency_light(self):
        # 课程承诺：不下载数据、不联网
        self.assertNotIn("http://", self.source)
        self.assertNotIn("https://", self.source)
        self.assertNotIn("下载", self.out)


if __name__ == "__main__":
    unittest.main(verbosity=2)
