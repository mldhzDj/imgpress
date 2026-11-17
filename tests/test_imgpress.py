"""imgpress 的单元测试，运行方式：

    python3 -m unittest discover -s tests -v
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import imgpress  # noqa: E402


def make_image(path: Path, size=(640, 480), color=(200, 30, 30), fmt=None) -> Path:
    """生成一张有噪点、不容易被压到极小的测试图。"""
    image = Image.new("RGB", size, color)
    pixels = image.load()
    for x in range(0, size[0], 3):
        for y in range(0, size[1], 3):
            if (x + y) % 2 == 0:
                pixels[x, y] = (x % 256, y % 256, (x * y) % 256)
    image.save(path, format=fmt)
    return path


class TestHelpers(unittest.TestCase):
    def test_human_size(self):
        self.assertEqual(imgpress.human_size(512), "512 B")
        self.assertEqual(imgpress.human_size(2048), "2.0 KB")
        self.assertEqual(imgpress.human_size(3 * 1024**2), "3.0 MB")

    def test_parse_size(self):
        self.assertEqual(imgpress.parse_size("10KB"), 10 * 1024)
        self.assertEqual(imgpress.parse_size("1.5MB"), int(1.5 * 1024**2))
        self.assertEqual(imgpress.parse_size("100"), 100)
        with self.assertRaises(Exception):
            imgpress.parse_size("abc")

    def test_find_images_and_target_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_image(root / "a.jpg")
            make_image(root / "b.png")
            (root / "sub").mkdir()
            make_image(root / "sub" / "c.jpg")
            (root / "note.txt").write_text("ignore me")

            found = imgpress.find_images(root, recursive=True)
            self.assertEqual(len(found), 3)
            self.assertEqual(len(imgpress.find_images(root, recursive=False)), 2)

            target = imgpress.target_path(root / "sub" / "c.jpg", root, root / "out", "webp")
            self.assertEqual(target, root / "out" / "sub" / "c.webp")

            target_jpg = imgpress.target_path(root / "b.png", root, root / "out", "jpeg")
            self.assertEqual(target_jpg.suffix, ".jpg")


class TestCompress(unittest.TestCase):
    def test_jpeg_gets_smaller(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = make_image(root / "big.jpg", size=(1600, 1200))
            out = root / "out"
            result = imgpress.compress_one(
                src, root, out, quality=60, max_width=None, max_height=None,
                out_format=None, strip_metadata=False, overwrite=False,
                min_bytes=0, skip_larger=True,
            )
            self.assertTrue(result.ok, result.note)
            self.assertLess(result.after, result.before)
            self.assertTrue((out / "big.jpg").exists())

    def test_resize_limits_long_edge(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = make_image(root / "wide.jpg", size=(2000, 1000))
            out = root / "out"
            result = imgpress.compress_one(
                src, root, out, quality=80, max_width=800, max_height=800,
                out_format=None, strip_metadata=False, overwrite=False,
                min_bytes=0, skip_larger=True,
            )
            self.assertTrue(result.ok, result.note)
            with Image.open(result.dst) as image:
                self.assertEqual(image.size, (800, 400))

    def test_min_size_skips(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = make_image(root / "tiny.jpg", size=(32, 32))
            result = imgpress.compress_one(
                src, root, root / "out", quality=80, max_width=None, max_height=None,
                out_format=None, strip_metadata=False, overwrite=False,
                min_bytes=10 * 1024, skip_larger=True,
            )
            self.assertFalse(result.ok)
            self.assertIn("跳过", result.note)

    def test_alpha_png_to_jpeg(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "alpha.png"
            image = Image.new("RGBA", (200, 200), (0, 0, 0, 0))
            image.paste((0, 200, 0, 255), (50, 50, 150, 150))
            image.save(src)

            result = imgpress.compress_one(
                src, root, root / "out", quality=85, max_width=None, max_height=None,
                out_format="jpeg", strip_metadata=False, overwrite=False,
                min_bytes=0, skip_larger=False,
            )
            self.assertTrue(result.ok, result.note)
            with Image.open(result.dst) as converted:
                self.assertEqual(converted.mode, "RGB")

    def test_main_end_to_end_with_json_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_image(root / "in" / "one.jpg") if (root / "in").mkdir() is None else None
            out = root / "out"
            report = root / "report.json"
            code = imgpress.main([
                str(root / "in"), "-o", str(out), "-q", "70", "--json", str(report),
            ])
            self.assertEqual(code, 0)
            self.assertTrue(report.exists())
            import json

            data = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(data["version"], imgpress.__version__)
            self.assertEqual(len(data["files"]), 1)
            self.assertTrue(data["files"][0]["ok"])


if __name__ == "__main__":
    unittest.main()
