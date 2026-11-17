# imgpress

批量压缩图片的小工具，命令行一条命令搞定。默认**不动原图**，结果输出到 `compressed/`，并告诉你一共省了多少体积。

```bash
python3 imgpress.py ~/Pictures -o ~/Pictures/compressed -q 80
```

## 特点

- 递归扫描目录，支持 `jpg / jpeg / png / webp / bmp / tiff`
- **自动纠正 EXIF 方向**，手机照片压缩后不会躺倒
- 可选按最长边缩放（`--max-width` / `--max-height`），等比、不放大
- **压缩后反而变大时自动保留原图**，不劣化画质
- 多线程处理，几百张图也很快
- 保留原目录结构输出，重名不会互相覆盖
- 支持 `--json` 输出结构化报告，方便接脚本
- 单个文件失败不影响整批，最后返回非 0 退出码

## 安装

```bash
pip install Pillow
```

只依赖 Pillow，没有其他第三方包。需要 Python 3.10+。

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

# 跳过小于 20KB 的小图，免得白忙
python3 imgpress.py ./photos --min-size 20KB

# 先看看会处理哪些文件，不动手
python3 imgpress.py ./photos --dry-run

# 去掉 EXIF 再存（发到网上前清理隐私信息）
python3 imgpress.py ./photos --strip

# 输出 JSON 报告，方便做统计
python3 imgpress.py ./photos --json report.json
```

| 参数 | 说明 | 默认 |
| --- | --- | --- |
| `paths` | 图片文件或目录，可给多个 | 必填 |
| `-o, --out` | 输出目录 | `compressed` |
| `-q, --quality` | JPEG/WebP 质量 1-100 | `82` |
| `--max-width` / `--max-height` | 缩放上限，取较大者作为最长边 | 不缩放 |
| `--format` | `jpeg` / `png` / `webp`，统一转换 | 保持原格式 |
| `--min-size` | 小于该体积跳过，支持 `10KB` / `1.5MB` | 不跳过 |
| `--no-skip-larger` | 压缩后变大也照常输出 | 保留原图 |
| `--no-recursive` | 只处理当前目录 | 递归 |
| `--strip` | 去掉元数据 | 否 |
| `--overwrite` | 覆盖已存在的输出 | 否 |
| `-j, --jobs` | 并发线程数 | CPU 数与 8 取小 |
| `--json` | 结果写入 JSON 报告 | 不写 |
| `--dry-run` | 只列文件不处理 | 否 |

## 输出示例

```
imgpress 0.2.0 · 共 128 个文件 → compressed
  ✓ IMG_2031.jpg  3.2 MB → 612.4 KB
  ✓ IMG_2032.jpg  2.8 MB → 540.1 KB
  ✓ icon.png  2.1 KB  (小于 20.0 KB，跳过)
--------------------------------------------------
处理 126 个，跳过/失败 2 个，用时 4.3s
体积 412.7 MB → 78.2 MB，节省 81.1%
```

## 说明

- GIF 默认跳过（压缩会丢动画帧）。
- PNG 转 JPEG 时会自动铺白底，避免透明区域变黑。
- 输出路径若与原图相同会拒绝执行，不会覆盖你的原始文件。
- 手机照片带 EXIF 方向信息的，会先按方向转正再压缩。

## 开发

```bash
pip install Pillow
python3 -m unittest discover -s tests -v
```

测试覆盖了体积解析、路径映射、缩放、格式转换、跳小图与 JSON 报告。

## 更新日志

### v0.2.0

- 新增 EXIF 方向自动纠正
- 新增 `--min-size`，跳过过小的图片
- 新增「压缩后变大则保留原图」，保证不劣化
- 新增 `--json` 结构化报告与 `--version`
- 新增 8 个单元测试
- 输出后缀统一：`jpeg` 转换后得到 `.jpg`

### v0.1.0

- 首版：递归扫描、等比缩放、多线程、格式转换、去元数据

## License

MIT，见 [LICENSE](LICENSE)。
