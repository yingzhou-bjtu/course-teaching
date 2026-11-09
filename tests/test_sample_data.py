# -*- coding: utf-8 -*-
"""data/sample 里 16 张真实照片的回归测试。

查三件事：文件在不在、尺寸对不对、许可表是否一一对应（少一条署名就算失败）。
"""

import io
import os
import struct
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAMPLE = os.path.join(ROOT, "data", "sample")
README = os.path.join(SAMPLE, "README.md")
PER_CLASS = 8
SIZE = 160


def jpeg_size(path):
    """从 JPEG 的 SOF 段里读宽高，不依赖 Pillow。"""
    with io.open(path, "rb") as f:
        data = f.read()
    if data[:2] != b"\xff\xd8":
        raise ValueError("不是 JPEG：" + path)
    pos = 2
    while pos < len(data) - 9:
        if data[pos] != 0xFF:
            pos += 1
            continue
        marker = data[pos + 1]
        if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
            pos += 2
            continue
        length = struct.unpack(">H", data[pos + 2:pos + 4])[0]
        if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
            height, width = struct.unpack(">HH", data[pos + 5:pos + 9])
            return width, height
        pos += 2 + length
    raise ValueError("找不到尺寸：" + path)


class SampleData(unittest.TestCase):
    def test_files_exist(self):
        for kind in ("cat", "dog"):
            folder = os.path.join(SAMPLE, kind)
            self.assertTrue(os.path.isdir(folder), "缺少目录：" + folder)
            names = sorted(n for n in os.listdir(folder) if n.lower().endswith((".jpg", ".jpeg")))
            self.assertEqual(len(names), PER_CLASS, "%s 应有 %d 张，实际 %d 张"
                             % (kind, PER_CLASS, len(names)))

    def test_size_is_160(self):
        for kind in ("cat", "dog"):
            for name in sorted(os.listdir(os.path.join(SAMPLE, kind))):
                if not name.lower().endswith((".jpg", ".jpeg")):
                    continue
                path = os.path.join(SAMPLE, kind, name)
                self.assertEqual(jpeg_size(path), (SIZE, SIZE), path)

    def test_license_table_covers_every_photo(self):
        with io.open(README, encoding="utf-8") as f:
            table = f.read()
        for kind in ("cat", "dog"):
            for name in sorted(os.listdir(os.path.join(SAMPLE, kind))):
                if not name.lower().endswith((".jpg", ".jpeg")):
                    continue
                self.assertIn("%s/%s" % (kind, name), table,
                              "data/sample/README.md 缺少 %s/%s 的署名行" % (kind, name))
        for license_name in ("CC BY", "CC BY-SA", "Public domain", "CC0"):
            self.assertIn(license_name, table, "许可列里没有出现 %s" % license_name)


if __name__ == "__main__":
    unittest.main(verbosity=2)
