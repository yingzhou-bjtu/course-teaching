# -*- coding: utf-8 -*-
"""确认 run.py 在没有 Jupyter 的情况下能跑通。"""

import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUN = os.path.join(ROOT, "run.py")
RUN_LITE = os.path.join(ROOT, "run_lite.py")


def run_fast(cwd):
    """显式按 UTF-8 解码，避免 Windows 控制台代码页把中文读坏。"""
    return subprocess.run(
        [sys.executable, RUN, "--fast"],
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=300,
        encoding="utf-8",
        errors="replace",
    )


class RunScript(unittest.TestCase):
    def test_fast_mode(self):
        proc = run_fast(ROOT)
        message = (proc.stdout or "") + (proc.stderr or "")
        self.assertEqual(proc.returncode, 0, message)
        self.assertIn("运行结束", proc.stdout or "")
        try:
            import matplotlib  # noqa: F401
        except ImportError:
            return
        figures = os.path.join(ROOT, "figures")
        self.assertTrue(os.path.isdir(figures), "没有生成 figures/ 目录")
        self.assertGreaterEqual(len(os.listdir(figures)), 5, "教学图不足五张")

    def test_lite_version_runs_with_stdlib_only(self):
        proc = subprocess.run(
            [sys.executable, RUN_LITE, "--fast"], cwd=ROOT,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=300, encoding="utf-8", errors="replace",
        )
        message = (proc.stdout or "") + (proc.stderr or "")
        self.assertEqual(proc.returncode, 0, message)
        self.assertIn("运行结束", proc.stdout or "")
        try:
            import matplotlib  # noqa: F401
        except ImportError:
            return
        figures = os.path.join(ROOT, "figures")
        self.assertTrue(os.path.isdir(figures), "没有生成 figures/ 目录")
        self.assertGreaterEqual(len(os.listdir(figures)), 5, "教学图不足五张")
        self.assertNotIn("numpy", (proc.stderr or "").lower())

    def test_missing_notebook_message(self):
        # 在别的目录执行时，入口应自己定位 notebook，不抛异常
        proc = run_fast(os.path.dirname(ROOT))
        message = (proc.stdout or "") + (proc.stderr or "")
        self.assertNotIn("Traceback", message)


if __name__ == "__main__":
    unittest.main(verbosity=2)
