# -*- coding: utf-8 -*-
"""ghfast 单元测试：只用标准库，Windows / macOS / Linux 均可直接跑。

    python -m unittest discover -s tests -v
"""

import functools
import hashlib
import http.server
import importlib.util
import os
import sys
import tempfile
import threading
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "ghfast", "ghfast.py")


def _load_ghfast():
    spec = importlib.util.spec_from_file_location("ghfast_under_test", SRC)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod  # dataclasses 需要能按模块名找回
    spec.loader.exec_module(mod)
    return mod


ghfast = _load_ghfast()


class TestUrlCandidates(unittest.TestCase):
    RAW = "https://raw.githubusercontent.com/octocat/Hello-World/master/README"
    RELEASE = "https://github.com/pytorch/pytorch/releases/download/v2.5.0/x.whl"
    ARCHIVE = "https://github.com/git/git/archive/refs/tags/v2.0.0.tar.gz"

    def test_raw_prefers_jsdelivr_and_keeps_original_last(self):
        cands = ghfast.download_candidates(self.RAW, [])
        self.assertTrue(any("cdn.jsdelivr.net/gh/octocat/Hello-World@master/README" in u
                            for u in cands))
        self.assertTrue(any("raw.gitmirror.com/octocat/Hello-World/master/README" in u
                            for u in cands))
        self.assertEqual(cands[-1], self.RAW)

    def test_mirror_prefix_is_applied(self):
        m = [ghfast.MirrorProbe("prefix", "https://ghproxy.net/")]
        self.assertEqual(ghfast.download_candidates(self.RELEASE, m)[0],
                         "https://ghproxy.net/" + self.RELEASE)

    def test_archive_uses_prefix(self):
        m = [ghfast.MirrorProbe("prefix", "https://ghproxy.net/")]
        cands = ghfast.download_candidates(self.ARCHIVE, m)
        self.assertTrue(any(u.startswith("https://ghproxy.net/https://github.com/git/git/archive")
                            for u in cands))

    def test_jsdelivr_needs_four_segments(self):
        self.assertIsNone(ghfast._jsdelivr_url("https://cdn.jsdelivr.net/gh/",
                                               "https://raw.githubusercontent.com/u/r/x"))

    def test_rawhost_rejects_other_hosts(self):
        self.assertIsNone(ghfast._rawhost_url("https://raw.gitmirror.com/", self.RELEASE))

    def test_dedup(self):
        self.assertEqual(ghfast._dedup(["a", "b", "a", "", "b"]), ["a", "b"])

    def test_mirror_url_kinds(self):
        self.assertEqual(ghfast.mirror_url(ghfast.MirrorProbe("prefix", "P/"), "U"), "P/U")
        self.assertEqual(ghfast.mirror_url(ghfast.MirrorProbe("jsdelivr", "J/"), self.RAW),
                         "J/octocat/Hello-World@master/README")
        self.assertEqual(ghfast.mirror_url(ghfast.MirrorProbe("rawhost", "R/"), self.RAW),
                         "R/octocat/Hello-World/master/README")
        self.assertEqual(ghfast.mirror_url(ghfast.MirrorProbe("prefix", "P/"), self.RELEASE),
                         "P/" + self.RELEASE)


class TestHosts(unittest.TestCase):
    BLOCK = ghfast.build_block([("1.2.3.4", "github.com"), ("5.6.7.8", "api.github.com")])

    def test_block_shape(self):
        self.assertIn(ghfast.HOSTS_BEGIN, self.BLOCK)
        self.assertIn(ghfast.HOSTS_END, self.BLOCK)
        self.assertIn("1.2.3.4", self.BLOCK)
        self.assertIn("github.com", self.BLOCK)

    def test_strip_keeps_foreign_lines(self):
        text = "127.0.0.1 localhost\n" + self.BLOCK + "10.0.0.1 corp\n"
        out = ghfast.strip_block(text)
        self.assertNotIn(ghfast.HOSTS_BEGIN, out)
        self.assertIn("127.0.0.1 localhost", out)
        self.assertIn("10.0.0.1 corp", out)

    def test_strip_is_idempotent(self):
        once = ghfast.strip_block("127.0.0.1 localhost\n" + self.BLOCK)
        self.assertEqual(ghfast.strip_block(once), once)

    def test_strip_handles_crlf(self):
        text = "127.0.0.1 localhost\r\n" + self.BLOCK.replace("\n", "\r\n")
        out = ghfast.strip_block(text)
        self.assertNotIn(ghfast.HOSTS_BEGIN, out)
        self.assertIn("127.0.0.1 localhost", out)

    def test_strip_without_block_is_harmless(self):
        text = "127.0.0.1 localhost\n"
        self.assertEqual(ghfast.strip_block(text), text)


class TestFormat(unittest.TestCase):
    def test_human_size(self):
        self.assertEqual(ghfast.human_size(999), "999 B")
        self.assertEqual(ghfast.human_size(1536), "1.5 KiB")
        self.assertEqual(ghfast.human_size(5 * 1024 ** 3), "5.0 GiB")

    def test_human_ms(self):
        self.assertEqual(ghfast.human_ms(None), "-")
        self.assertEqual(ghfast.human_ms(9.7), "9.7 ms")
        self.assertEqual(ghfast.human_ms(91.2), "91 ms")

    def test_east_asian_width(self):
        self.assertEqual(ghfast.width("域名"), 4)
        self.assertEqual(ghfast.pad("域名", 6), "域名  ")
        self.assertEqual(ghfast.width("ab"), 2)


class TestGit(unittest.TestCase):
    def test_insteadof_pairs(self):
        pairs = ghfast.insteadof_pairs("https://ghproxy.net/")
        self.assertEqual(pairs[0], ("https://github.com/",
                                    "https://ghproxy.net/https://github.com/"))
        self.assertEqual(pairs[1][0], "https://raw.githubusercontent.com/")


class TestState(unittest.TestCase):
    def test_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            old_file, old_dir = ghfast.STATE_FILE, ghfast.CONFIG_DIR
            try:
                ghfast.CONFIG_DIR = tmp
                ghfast.STATE_FILE = os.path.join(tmp, "state.json")
                ghfast.save_state({"git_insteadof": [["a", "b"]]})
                self.assertEqual(ghfast.load_state()["git_insteadof"], [["a", "b"]])
                self.assertEqual(ghfast.load_state()["git_insteadof"][0][1], "b")
            finally:
                ghfast.STATE_FILE, ghfast.CONFIG_DIR = old_file, old_dir

    def test_missing_state_is_empty(self):
        old = ghfast.STATE_FILE
        try:
            ghfast.STATE_FILE = os.path.join(tempfile.gettempdir(), "ghfast-no-such.json")
            self.assertEqual(ghfast.load_state(), {})
        finally:
            ghfast.STATE_FILE = old


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):  # 静音
        pass

    def do_GET(self):
        if self.path.startswith("/err.bin"):
            return self._html_error()
        # 故意不支持 Range，用来验证「服务端不支持续传」的降级路径
        if self.headers.get("Range"):
            self.send_response(200)
            data = self._payload()
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        super().do_GET()

    def _payload(self):
        with open(os.path.join(self.directory, "blob.bin"), "rb") as f:
            return f.read()

    def do_HEAD(self):
        if self.path.startswith("/err.bin"):
            return self._html_error()
        super().do_HEAD()

    def _html_error(self):
        body = b"<!DOCTYPE html><html><body>proxy error</body></html>"
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)


class TestDownload(unittest.TestCase):
    """用本机临时 HTTP 服务验证下载链路（不依赖外网）。"""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.payload = bytes(range(256)) * 16
        with open(os.path.join(cls.tmp.name, "blob.bin"), "wb") as f:
            f.write(cls.payload)
        handler = functools.partial(_QuietHandler, directory=cls.tmp.name)
        cls.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = "http://127.0.0.1:%d/blob.bin" % cls.httpd.server_address[1]

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.tmp.cleanup()

    def test_probe_download(self):
        r = ghfast.probe_download(self.url, timeout=5)
        self.assertIsNotNone(r)
        self.assertEqual(r[0], self.url)

    def test_download_full(self):
        with tempfile.TemporaryDirectory() as out_dir:
            out = os.path.join(out_dir, "blob.bin")
            okk, msg = ghfast.download_to(self.url, out, timeout=10)
            self.assertTrue(okk, msg)
            with open(out, "rb") as f:
                self.assertEqual(f.read(), self.payload)
            self.assertFalse(os.path.exists(out + ".part"))
            self.assertEqual(ghfast.sha256_file(out),
                             hashlib.sha256(self.payload).hexdigest())

    def test_proxy_html_error_page_is_skipped(self):
        url = self.url.replace("/blob.bin", "/err.bin")
        self.assertIsNone(ghfast.probe_download(url, timeout=5))
        with tempfile.TemporaryDirectory() as out_dir:
            out = os.path.join(out_dir, "x.bin")
            okk, msg = ghfast.download_to(url, out, timeout=5)
            self.assertFalse(okk)
            self.assertIn("HTML", msg)
            self.assertFalse(os.path.exists(out))

    def test_download_resume_falls_back_when_server_ignores_range(self):
        with tempfile.TemporaryDirectory() as out_dir:
            out = os.path.join(out_dir, "blob.bin")
            with open(out + ".part", "wb") as f:  # 残留半截文件
                f.write(self.payload[:100])
            okk, msg = ghfast.download_to(self.url, out, timeout=10)
            self.assertTrue(okk, msg)
            with open(out, "rb") as f:
                self.assertEqual(f.read(), self.payload)


class TestProxyErrorGuard(unittest.TestCase):
    """镜像会把错误页以 200 + text/html 返回，必须识别出来换下一个来源。"""

    def test_detects_html_error_page(self):
        body = b"<!DOCTYPE html><html><body>404</body></html>"
        self.assertTrue(ghfast._looks_like_proxy_error(
            "https://raw.githubusercontent.com/u/r/main/README.md", "text/html", body))

    def test_real_html_files_are_not_rejected(self):
        body = b"<!DOCTYPE html><html></html>"
        self.assertFalse(ghfast._looks_like_proxy_error(
            "https://raw.githubusercontent.com/u/r/main/index.html", "text/html", body))

    def test_plain_text_is_not_rejected(self):
        self.assertFalse(ghfast._looks_like_proxy_error(
            "https://raw.githubusercontent.com/u/r/main/README.md", "text/plain", b"# hello"))

    def test_binary_is_not_rejected(self):
        self.assertFalse(ghfast._looks_like_proxy_error(
            "https://github.com/u/r/releases/download/v1/x.whl", "application/octet-stream",
            b"PK\x03\x04"))

class TestCli(unittest.TestCase):
    def test_all_subcommands_have_handlers(self):
        parser = ghfast.build_parser()
        for cmd in ("doctor", "hosts", "mirrors", "download", "clone", "git",
                    "pip", "install", "selftest"):
            ns = parser.parse_args([cmd] + (["x"] if cmd in ("download", "clone") else []))
            self.assertTrue(callable(ns.func), cmd)

    def test_global_flag_after_subcommand(self):
        parser = ghfast.build_parser()
        self.assertEqual(parser.parse_args(["--timeout", "3", "mirrors"]).timeout, 3.0)
        self.assertEqual(parser.parse_args(["mirrors", "--timeout", "4"]).timeout, 4.0)
        self.assertEqual(parser.parse_args(["mirrors"]).workers, 10)

    def test_clone_options_are_not_leaked_to_git(self):
        # 回归测试：曾经用 REMAINDER 收集透传参数，导致 -d/--dest 被当成 git 的开关
        ns = ghfast.build_parser().parse_args(
            ["clone", "https://github.com/a/b", "-d", "/tmp/x", "--depth", "1",
             "-b", "dev", "-j", "2", "--recursive", "--git-arg=--filter=blob:none"])
        self.assertEqual(ns.dest, "/tmp/x")
        self.assertEqual(ns.depth, 1)
        self.assertEqual(ns.branch, "dev")
        self.assertEqual(ns.jobs, 2)
        self.assertTrue(ns.recursive)
        self.assertEqual(ns.git_args, ["--filter=blob:none"])
        self.assertFalse(hasattr(ns, "rest"))

    def test_hosts_defaults(self):
        ns = ghfast.build_parser().parse_args(["hosts"])
        self.assertFalse(ns.apply)
        self.assertFalse(ns.restore)


if __name__ == "__main__":
    unittest.main(verbosity=2)
