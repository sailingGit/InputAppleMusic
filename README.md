# 网易云歌单一次性导入 Apple Music

这是基于上游 `InputAppleMusic` 改造的个人迁移工具。推荐使用根目录的
`netease_to_apple_music.py`：它会先读取网易云歌单并匹配 Apple Music，生成
JSON/CSV 预览报告；只有明确传入 `--commit` 并完成确认后，才会创建一个新的
Apple Music 歌单。

## 适合的场景

- 网易云“我喜欢的音乐”或普通歌单一次性搬家。
- Apple Music 为美区、日区、港区等外区账号。
- 希望在真正写入前检查错配、Live、翻唱和无版权歌曲。
- 只新增一个歌单，不修改或删除已有 Apple Music 内容。

## 安全设计

- 默认仅预览，不写 Apple Music。
- 自动读取当前 Apple Music 账号的 storefront，不再写死中国区。
- 高置信度曲目和“需要复核”曲目分开；后者默认不导入。
- 真正写入时创建新歌单，不删除、清空或重排现有歌单。
- `media-user-token` 使用隐藏输入，不写入配置文件或迁移报告。
- `reports/` 已加入 `.gitignore`，避免个人歌单数据被提交。

## 环境要求

- Python 3.10+
- 有效的 Apple Music 订阅
- 能在浏览器登录 [Apple Music 网页版](https://music.apple.com)

## 安装

```bash
git clone https://github.com/sailingGit/InputAppleMusic.git
cd InputAppleMusic
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-once.txt
```

## 取得 Apple Music 用户令牌

1. 浏览器打开 [music.apple.com](https://music.apple.com) 并登录。
2. 打开开发者工具。
3. 在 Application（应用）→ Cookies → `https://music.apple.com` 中找到
   `media-user-token`。
4. 运行脚本后，在隐藏输入提示中粘贴该值。

不要把该令牌发给别人、放进命令参数或提交到 GitHub。脚本会自动从 Apple
Music 网页资源取得临时 developer token，通常不需要手工复制 Bearer Token。

## 第一步：小规模预览

从网易云复制“我喜欢的音乐”的分享链接，然后运行：

```bash
python netease_to_apple_music.py "网易云分享链接" --limit 20
```

默认不会修改 Apple Music。完成后检查 `reports/` 中的：

- `migration-*.csv`：适合直接查看歌曲和匹配结果。
- `migration-*.json`：包含完整匹配信息。

结果分为：

- `matched`：达到自动导入阈值。
- `needs_review`：可能正确，但需要人工复核，默认不导入。
- `unmatched`：没有可信匹配。
- `error`：请求或接口错误。

## 第二步：小规模真实导入

检查 20 首的结果没有明显错配后：

```bash
python netease_to_apple_music.py "网易云分享链接" \
  --limit 20 \
  --target-name "网易云迁移测试" \
  --commit
```

脚本会显示即将导入的数量，并要求输入形如 `IMPORT 18` 的确认文本。确认后才会
创建新歌单并写入。

## 第三步：迁移完整歌单

```bash
python netease_to_apple_music.py "网易云分享链接" \
  --target-name "网易云我喜欢的音乐" \
  --commit
```

脚本会自动调用 `/v1/me/storefront` 检测账号地区。如果确实需要覆盖搜索地区，可加：

```bash
--storefront us
```

不建议无理由覆盖，因为账号地区与搜索地区不一致可能造成不可播放或无法写入。

## 私密“我喜欢的音乐”读取失败

公开分享链接通常不需要登录。如果网易云只返回部分歌曲或提示无法读取，可在当前
终端临时提供网易云 `MUSIC_U` Cookie：

```bash
read -s NETEASE_MUSIC_U
export NETEASE_MUSIC_U
python netease_to_apple_music.py "网易云分享链接" --limit 20
unset NETEASE_MUSIC_U
```

`read -s` 输入不会显示。不要把 Cookie 写进仓库文件。

## 可选参数

```text
--target-name NAME    新建的 Apple Music 歌单名称
--storefront us       覆盖自动检测的 Apple Music 地区
--auto-score 82       自动导入阈值
--review-score 68     人工复核阈值
--include-review      同时导入 needs_review（风险更高）
--limit 20            只处理前 N 首
--commit              允许在预览后创建并写入新歌单
--yes                 跳过最终确认，仅适合已经验证过的自动运行
```

## 旧版 GUI 与酷狗脚本

上游原有代码仍保留在 `导入applemusic/` 下，包括 PyQt6 GUI、网易云脚本和酷狗
脚本。这些旧入口仍将 Apple Music 搜索地区写死为 `cn`，也没有新的预览确认保护；
外区账号请优先使用根目录的一次性脚本。

如需运行旧版 GUI，再安装完整依赖：

```bash
python -m pip install -r requirements.txt
python 导入applemusic/music_transfer_gui.py
```

## 测试

```bash
python -m unittest discover -s tests -v
python -m py_compile netease_to_apple_music.py
```

## 已知限制

- 网易云与 Apple Music 曲库、歌名和发行版本不同，不可能做到 100% 自动匹配。
- Apple Music 和网易云网页端接口可能变化，令牌也会过期。
- “我喜欢”的红心状态、播放次数、评论和下载文件不会迁移；迁移结果是普通播放列表。
- 中途网络失败可能留下一个只写入部分歌曲的新歌单。报告会记录其歌单 ID，脚本不会
  自动删除它。

## 许可证

本 Fork 延续上游仓库的 MIT 许可证。内嵌的 `pyncm` 保留其自身许可证。
