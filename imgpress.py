#!/usr/bin/env python3
"""imgpress — 批量压缩图片的命令行小工具。

特点：
  * 递归扫描目录，支持 jpg / png / webp / bmp / tiff
  * 可选按最长边缩放，保持宽高比
  * 多线程处理，速度快
  * 默认输出到 ./compressed，保留原目录结构，不覆盖原图
  * 打印压缩前后对比，方便判断效果

用法见 README.md，或运行 `python3 imgpress.py --help`。
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    sys.stderr.write("缺少依赖 Pillow，请先运行：pip install Pillow\n")
    raise SystemExit(2)

SUPPORTED_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}
# GIF 有动画帧，压缩会丢动画，默认跳过
SKIPPED_SUFFIXES = {".gif"}
# 这些格式不支持透明通道，转格式时要先铺白底
NO_ALPHA_FORMATS = {"JPEG"}


@dataclass
class Result:
    """单个文件的处理结果。"""

    src: Path
    dst: Path | None
    before: int
    after: int
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None and self.dst is not None

    @property
    def saved(self) -> int:
        return max(self.before - self.after, 0)

    @property
    def ratio(self) -> float:
        if self.before <= 0:
            return 0.0
        return self.after / self.before


def human_size(num: int) -> str:
    """把字节数转成人类可读的大小。"""
    size = float(num)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
        size /= 1024
    return f"{size:.1f} GB"


def find_images(root: Path, recursive: bool) -> list[Path]:
    """在 root 下找出所有支持的图片文件。"""
    if root.is_file():
        return [root] if root.suffix.lower() in SUPPORTED_SUFFIXES else []

    pattern = root.rglob("*") if recursive else root.glob("*")
    files = [
        p
        for p in pattern
        if p.is_file() and p.suffix.lower() in SUPPORTED_SUFFIXES
    ]
    return sorted(files)


def target_path(src: Path, root: Path, out_dir: Path, out_format: str | None) -> Path:
    """算出输出路径：保留相对目录结构，必要时改扩展名。"""
    if src.is_file() and src.parent != root:
        rel = Path(src.name)
    else:
        try:
            rel = src.relative_to(root)
        except ValueError:
            rel = Path(src.name)

    if out_format:
        rel = rel.with_suffix(f".{out_format.lower()}")

    return out_dir / rel


def flatten(image: Image.Image, background: tuple[int, int, int] = (255, 255, 255)) -> Image.Image:
    """把带透明通道的图铺到纯色底上，供 JPEG 这类不支持透明的格式使用。"""
    if image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info):
        rgba = image.convert("RGBA")
        canvas = Image.new("RGB", rgba.size, background)
        canvas.paste(rgba, mask=rgba.split()[-1])
        return canvas
    if image.mode not in ("RGB", "L"):
        return image.convert("RGB")
    return image


def resize_if_needed(image: Image.Image, max_width: int | None, max_height: int | None) -> Image.Image:
    """按最长边等比缩放；不放大原图。"""
    limits = [v for v in (max_width, max_height) if v]
    if not limits:
        return image

    limit = max(limits)
    width, height = image.size
    longest = max(width, height)
    if longest <= limit:
        return image

    scale = limit / longest
    new_size = (max(1, round(width * scale)), max(1, round(height * scale)))
    return image.resize(new_size, Image.LANCZOS)


def compress_one(
    src: Path,
    root: Path,
    out_dir: Path,
    quality: int,
    max_width: int | None,
    max_height: int | None,
    out_format: str | None,
    strip_metadata: bool,
    overwrite: bool,
) -> Result:
    """压缩单个文件，返回处理结果（不抛异常，错误记在 Result 里）。"""
    before = src.stat().st_size
    dst = target_path(src, root, out_dir, out_format)

    if dst.resolve() == src.resolve():
        return Result(src, None, before, before, "输出路径与原图相同，跳过（换个 --out 目录）")
    if dst.exists() and not overwrite:
        return Result(src, None, before, before, "目标已存在，跳过（用 --overwrite 覆盖）")

    dst.parent.mkdir(parents=True, exist_ok=True)

    try:
        with Image.open(src) as image:
            image.load()
            fmt = (out_format or src.suffix.lstrip(".")).upper()
            if fmt == "JPG":
                fmt = "JPEG"
            image = resize_if_needed(image, max_width, max_height)
            if fmt in NO_ALPHA_FORMATS:
                image = flatten(image)

            save_kwargs: dict[str, object] = {}
            if fmt in {"JPEG", "WEBP"}:
                save_kwargs["quality"] = quality
                save_kwargs["method"] = 6 if fmt == "WEBP" else None
            if fmt == "PNG":
                save_kwargs["optimize"] = True
            if fmt == "JPEG" and strip_metadata:
                save_kwargs["exif"] = b""

            save_kwargs = {k: v for k, v in save_kwargs.items() if v is not None}
            image.save(dst, format=fmt, **save_kwargs)

        after = dst.stat().st_size
        return Result(src, dst, before, after)
    except Exception as exc:  # noqa: BLE001 - 单个文件失败不该中断整批
        return Result(src, None, before, before, f"{type(exc).__name__}: {exc}")


def run(
    files: Sequence[Path],
    root: Path,
    out_dir: Path,
    quality: int,
    max_width: int | None,
    max_height: int | None,
    out_format: str | None,
    strip_metadata: bool,
    overwrite: bool,
    jobs: int,
) -> list[Result]:
    """并发处理一批文件。"""
    results: list[Result] = []
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        futures = {
            pool.submit(
                compress_one,
                f,
                root,
                out_dir,
                quality,
                max_width,
                max_height,
                out_format,
                strip_metadata,
                overwrite,
            ): f
            for f in files
        }
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            status = "✓" if result.ok else "✗"
            if result.ok:
                print(
                    f"  {status} {result.src.name}  "
                    f"{human_size(result.before)} → {human_size(result.after)}"
                )
            else:
                print(f"  {status} {result.src.name}  {result.error}")
    return results


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="imgpress",
        description="批量压缩图片，输出到新目录，不动原图。",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("paths", nargs="+", help="图片文件或目录，可以给多个")
    parser.add_argument("-o", "--out", default="compressed", help="输出目录")
    parser.add_argument("-q", "--quality", type=int, default=82, help="JPEG/WebP 质量，1-100")
    parser.add_argument("--max-width", type=int, default=None, help="缩放后的最大宽度（像素）")
    parser.add_argument("--max-height", type=int, default=None, help="缩放后的最大高度（像素）")
    parser.add_argument(
        "--format",
        default=None,
        choices=["jpeg", "jpg", "png", "webp"],
        help="统一转成指定格式；默认保持原格式",
    )
    parser.add_argument("--no-recursive", action="store_true", help="只处理当前目录，不进子目录")
    parser.add_argument("--strip", action="store_true", help="去掉 EXIF 等元数据（JPEG）")
    parser.add_argument("--overwrite", action="store_true", help="允许覆盖已存在的输出文件")
    parser.add_argument("-j", "--jobs", type=int, default=min(8, (os.cpu_count() or 4)), help="并发线程数")
    parser.add_argument("--dry-run", action="store_true", help="只列出将要处理的文件")
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)

    if not 1 <= args.quality <= 100:
        print("错误：--quality 必须在 1-100 之间", file=sys.stderr)
        return 2

    out_dir = Path(args.out).expanduser()
    roots = [Path(p).expanduser() for p in args.paths]
    missing = [str(p) for p in roots if not p.exists()]
    if missing:
        print(f"错误：找不到路径 {', '.join(missing)}", file=sys.stderr)
        return 2

    recursive = not args.no_recursive
    files: list[Path] = []
    for root in roots:
        files.extend(find_images(root, recursive))

    if not files:
        print("没有找到可处理的图片（支持 jpg/png/webp/bmp/tiff）")
        return 0

    if args.dry_run:
        print(f"将要处理 {len(files)} 个文件：")
        for f in files:
            print(f"  {f}  ({human_size(f.stat().st_size)})")
        return 0

    print(f"共 {len(files)} 个文件 → {out_dir}")
    started = time.time()
    results = run(
        files=files,
        root=roots[0] if len(roots) == 1 else Path("."),
        out_dir=out_dir,
        quality=args.quality,
        max_width=args.max_width,
        max_height=args.max_height,
        out_format=args.format,
        strip_metadata=args.strip,
        overwrite=args.overwrite,
        jobs=max(1, args.jobs),
    )

    ok = [r for r in results if r.ok]
    failed = [r for r in results if not r.ok]
    before = sum(r.before for r in ok)
    after = sum(r.after for r in ok)
    elapsed = time.time() - started

    print("-" * 46)
    print(f"成功 {len(ok)} 个，跳过/失败 {len(failed)} 个，用时 {elapsed:.1f}s")
    if before:
        delta = 100 * (1 - after / before)
        if delta >= 0:
            print(f"体积 {human_size(before)} → {human_size(after)}，节省 {delta:.1f}%")
        else:
            print(f"体积 {human_size(before)} → {human_size(after)}，增大 {-delta:.1f}%（原图本来就很小）")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
