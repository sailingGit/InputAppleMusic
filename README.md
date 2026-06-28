# Apple Music 歌单迁移工具

将你的**网易云音乐**或**酷狗音乐**歌单一键导入 **Apple Music**。

## 功能亮点

- **双平台支持** — 网易云音乐 / 酷狗音乐均可作为源平台
- **精美图形界面** — 基于 PyQt6 构建，操作直观
- **多线程并发导入** — 可调节线程数与请求间隔，平衡速度与稳定性
- **智能限流保护** — 自动检测 Apple Music API 429 限流并指数退避重试
- **失败列表导出** — 导入失败的歌曲会自动记录，支持导出为 JSON 文件
- **数据清洗** — 自动去除括号后缀、合并歌手信息，提高搜索匹配率

## 环境要求

- Python 3.10+
- Chrome 浏览器（酷狗歌单抓取需要）

## 安装

```bash
# 克隆仓库
git clone https://github.com/你的用户名/apple-music-transfer.git
cd apple-music-transfer

# 安装依赖
pip install -r requirements.txt
```

## 快速开始

### 图形界面模式（推荐）

```bash
python 导入applemusic/music_transfer_gui.py
```

1. 选择来源平台（网易云/酷狗）
2. 填写歌单链接或 ID
3. 填写 Apple Music 配置（见下方说明）
4. 点击「开始迁移」

### 命令行模式

**网易云音乐导入：**

```bash
python 导入applemusic/多线程网易云导入AppleMusic.py
```

**酷狗音乐导入：**

```bash
python 导入applemusic/多线程酷狗导入applemusic.py
```

> **注意**：命令行模式会从项目根目录的 `config.json` 自动读取 Token，请先配置好该文件（见下方说明）。

## 配置说明

在项目根目录创建 `config.json`（已自动纳入 `.gitignore`，不会上传到 GitHub）：

```json
{
  "bearer_token": "你的 Bearer Token",
  "user_token": "你的 User Token",
  "playlist_id": "你的目标歌单 ID（以 p. 开头）"
}
```

### Apple Music 凭证说明

使用本工具需要提供以下 Apple Music API 凭证：

| 配置项 | 说明 | 获取方式 |
|--------|------|----------|
| **目标歌单 ID** | Apple Music 中目标歌单的 ID（以 `p.` 开头） | 在 Apple Music 创建歌单后，从分享链接中获取 |
| **Bearer Token** | 开发者临时授权令牌 | 从 Apple Music Web 请求头中获取 |
| **User Token** | 用户身份授权令牌 | 从 Apple Music Web 请求头中获取 |

> **Token 有效期**：通常为 24 小时左右，过期后需要重新抓取。

### 获取 Token 的方法

1. 打开浏览器，登录 [music.apple.com](https://music.apple.com)
2. 按 `F12` 打开开发者工具
3. 切换到「网络」(Network) 标签
4. 刷新页面，任意找一个 API 请求
5. 在请求头中复制 `Authorization`（Bearer Token）和 `music-user-token`（User Token）

## 项目结构

```
├── 导入applemusic/
│   ├── music_transfer_gui.py             # PyQt6 图形界面
│   ├── 多线程网易云导入AppleMusic.py      # 网易云 → Apple Music 导入脚本
│   ├── 多线程酷狗导入applemusic.py        # 酷狗 → Apple Music 导入脚本
│   └── pyncm/                            # 网易云 API 解密库（第三方）
├── config.json                     # 配置文件（已 gitignore，需自行创建）
├── .gitignore
├── LICENSE
├── requirements.txt
└── README.md
```

## 工作原理

```
┌─────────────────┐     ┌─────────────────┐     ┌──────────────────┐
│  网易云音乐       │     │  酷狗音乐        │     │                  │
│  (pyncm API)     │     │ (Selenium 抓取)  │     │   Apple Music    │
│         │        │     │        │         │     │   API 导入       │
│  提取歌单数据     │     │  提取歌单数据     │     │                  │
└────────┬────────┘     └────────┬─────────┘     └────────┬─────────┘
         │                       │                        │
         └───────────┬───────────┘                        │
                     │                                    │
                     ▼                                    ▼
              ┌──────────────┐                  ┌──────────────────┐
              │ 数据清洗模块   │                  │  搜索匹配歌曲      │
              │ 去除冗余信息   │ ──────────────►  │  写入目标歌单      │
              └──────────────┘                  └──────────────────┘
```

## 依赖

- [PyQt6](https://pypi.org/project/PyQt6/) — 图形界面
- [requests](https://pypi.org/project/requests/) — HTTP 请求
- [BeautifulSoup4](https://pypi.org/project/beautifulsoup4/) — HTML 解析
- [selenium](https://pypi.org/project/selenium/) — 浏览器自动化（酷狗抓取）
- [webdriver-manager](https://pypi.org/project/webdriver-manager/) — ChromeDriver 自动管理
- [pyncm](https://github.com/greats3an/pyncm) — 网易云音乐 API（内嵌）

## 免责声明

- 本工具仅供学习交流使用，请勿用于商业用途
- 使用本工具时请遵守 Apple Music 服务条款
- 使用者需自行承担因使用本工具产生的任何风险和责任
- Token 涉及个人信息，请勿提交到公共仓库

## 开源协议

[MIT](LICENSE)
