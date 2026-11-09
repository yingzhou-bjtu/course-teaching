# -*- coding: utf-8 -*-
"""确认 run.py 在没有 Jupyter 的情况下能跑通。"""

import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUN = os.path.join(ROOT, "run.py")


class RunScript(unittest.TestCase):
    def test_fast_mode(self):
        proc = subprocess.run([sys.executable, RUN, "--fast"], cwd=ROOT,
                              capture_output=True, text=True, timeout=300)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("运行结束", proc.stdout)

    def test_missing_notebook_message(self):
        # 在别的目录执行时，应给出可读提示而不是一屏报错
        proc = subprocess.run([sys.executable, RUN, "--fast"], cwd=os.path.dirname(ROOT),
                              capture_output=True, text=True, timeout=300)
        self.assertNotIn("Traceback", proc.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
