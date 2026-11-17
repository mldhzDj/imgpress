# imgpress

批量压缩图片的小工具，命令行一条命令搞定。默认**不动原图**，结果输出到 `compressed/`，并告诉你一共省了多少体积。

```bash
python3 imgpress.py ~/Pictures -o ~/Pictures/compressed -q 80
```

## 特点

- 递归扫描目录，支持 `jpg / jpeg / png / webp / bmp / tiff`
- 可选按最长边缩放（`--max-width` / `--max-height`），等比、不放大
- 多线程处理，几百张图也很快
- 保留原目录结构输出，重名不会互相覆盖
- 每个文件打印压缩前后大小，最后给出总节省比例
- 单个文件失败不影响整批，最后返回非 0 退出码

## 安装

```bash
pip install Pillow
```

只依赖 Pillow，没有其他第三方包。

## 用法

```bash
# 最常用：压缩当前目录（含子目录）里的所有图片
python3 imgpress.py .

# 指定质量和输出目录
python3 imgpress.py ./photos -o ./photos_small -q 75

# 顺手把长边缩到 2000px 以内
python3 imgpress.py ./photos -o ./photos_small --max-width 2000 --max-height 2000

# 全部转成 webp（体积通常再小一截）
python3 imgpress.py ./photos -o ./photos_webp --format webp -q 80

# 先看看会处理哪些文件，不动手
python3 imgpress.py ./photos --dry-run

# 去掉 EXIF 再存（发到网上前清理隐私信息）
python3 imgpress.py ./photos --strip
```

| 参数 | 说明 | 默认 |
| --- | --- | --- |
| `paths` | 图片文件或目录，可给多个 | 必填 |
| `-o, --out` | 输出目录 | `compressed` |
| `-q, --quality` | JPEG/WebP 质量 1-100 | `82` |
| `--max-width` / `--max-height` | 缩放上限，取较大者作为最长边 | 不缩放 |
| `--format` | `jpeg` / `png` / `webp`，统一转换 | 保持原格式 |
| `--no-recursive` | 只处理当前目录 | 递归 |
| `--strip` | 去掉元数据 | 否 |
| `--overwrite` | 覆盖已存在的输出 | 否 |
| `-j, --jobs` | 并发线程数 | CPU 数与 8 取小 |
| `--dry-run` | 只列文件不处理 | 否 |

## 输出示例

```
共 128 个文件 → compressed
  ✓ IMG_2031.jpg  3.2 MB → 612.4 KB
  ✓ IMG_2032.jpg  2.8 MB → 540.1 KB
--------------------------------------------------
成功 128 个，跳过/失败 0 个，用时 4.3s
体积 412.7 MB → 78.2 MB，节省 81.1%
```

## 说明

- GIF 默认跳过（压缩会丢动画帧）。
- PNG 转 JPEG 时会自动铺白底，避免透明区域变黑。
- 输出路径若与原图相同会拒绝执行，不会覆盖你的原始文件。

## License

MIT，见 [LICENSE](LICENSE)。
