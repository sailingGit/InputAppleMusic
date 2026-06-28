import time
import re
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager
from concurrent.futures import ThreadPoolExecutor, as_completed  # 🌟 引入多线程并发模块


def 提取酷狗虚拟列表歌单(目标链接):
    """
    模块一：抓取酷狗歌单数据
    """
    浏览器配置 = Options()
    浏览器配置.add_argument("--disable-gpu")
    浏览器配置.add_argument("--headless")  # 后台静默运行
    浏览器配置.add_argument(
        "--user-agent=Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1")

    print("🚀 正在启动自动化浏览器提取酷狗数据...")
    驱动服务 = Service(ChromeDriverManager().install())
    浏览器引擎 = webdriver.Chrome(service=驱动服务, options=浏览器配置)

    已抓取_指纹集合 = set()
    完整播放列表 = []

    try:
        浏览器引擎.get(目标链接)
        print("⏳ 正在等待首屏数据渲染...")
        WebDriverWait(浏览器引擎, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'span[class*="songItem_songName"]'))
        )

        print("⏬ 启动锚点追踪滚动算法...")
        连续未新增_计数器 = 0

        while True:
            页面渲染源码 = 浏览器引擎.page_source
            文档对象模型 = BeautifulSoup(页面渲染源码, "html.parser")
            可视区域_节点集合 = 文档对象模型.select('div[class*="songItem_songItem"]')

            当前视口_新增数 = 0

            for 歌曲节点 in 可视区域_节点集合:
                名称_节点 = 歌曲节点.select_one('[class*="songItem_songName"]')
                歌手_节点 = 歌曲节点.select_one('[class*="songItem_singer"]')

                if 名称_节点 and 歌手_节点:
                    文本_歌名 = 名称_节点.get_text(strip=True)
                    文本_歌手 = 歌手_节点.get_text(strip=True)
                    特征元组 = (文本_歌名, 文本_歌手)

                    if 特征元组 not in 已抓取_指纹集合:
                        已抓取_指纹集合.add(特征元组)
                        完整播放列表.append({"song_name": 文本_歌名, "artist": 文本_歌手})
                        当前视口_新增数 += 1

            if 当前视口_新增数 > 0:
                连续未新增_计数器 = 0
                print(f"✅ 抓取推进：当前累计 {len(已抓取_指纹集合)} 首")
            else:
                连续未新增_计数器 += 1

            if 连续未新增_计数器 >= 5:
                print("🏁 已达列表底部，抓取结束！")
                break

            当前所有真实节点 = 浏览器引擎.find_elements(By.CSS_SELECTOR, 'div[class*="songItem_songItem"]')
            if 当前所有真实节点:
                最后一个节点 = 当前所有真实节点[-1]
                浏览器引擎.execute_script("arguments[0].scrollIntoView({block: 'center'});", 最后一个节点)

            time.sleep(1.5)

        return 完整播放列表
    except Exception as 错误对象:
        print(f"❌ 提取发生异常: {错误对象}")
        return 完整播放列表
    finally:
        浏览器引擎.quit()


def 深度清洗文本(歌名, 歌手):
    """
    模块二：数据清洗过滤器
    """
    干净_歌名 = re.sub(r'\(.*?\)|（.*?）|\[.*?\]|【.*?】', '', 歌名).strip()
    干净_歌手 = re.split(r'[/&]', 歌手)[0].strip()
    return 干净_歌名, 干净_歌手


def 向苹果曲库导入单首歌曲(文本_歌名, 文本_歌手, 开发者临时凭证, 用户授权凭证, 目标歌单ID):
    """
    模块三：苹果音乐 API 调用写入 (包含 429 限流重试机制)
    """
    请求头配置 = {
        "Authorization": f"Bearer {开发者临时凭证}",
        "music-user-token": 用户授权凭证,
        "Origin": "https://music.apple.com",
        "Content-Type": "application/json"
    }

    搜索_基础接口 = "https://api.music.apple.com/v1/catalog/cn/search"
    请求_网址 = f"{搜索_基础接口}?term={文本_歌名} {文本_歌手}&types=songs&limit=1"

    最大重试次数 = 3
    for 尝试次数 in range(最大重试次数):
        try:
            响应_搜索结果 = requests.get(请求_网址, headers=请求头配置)

            # 🌟 核心防封逻辑：如果触发了苹果的 429 限制，强制让这个线程休息 2 秒再试
            if 响应_搜索结果.status_code == 429:
                print(f"⚠️ [触发限流] {文本_歌名} 正在排队重试...")
                time.sleep(2)
                continue

            if 响应_搜索结果.status_code == 200:
                解析_数据字典 = 响应_搜索结果.json()

                if "songs" in 解析_数据字典["results"] and len(解析_数据字典["results"]["songs"]["data"]) > 0:
                    歌曲_内部身份码 = 解析_数据字典["results"]["songs"]["data"][0]["id"]

                    写入_接口地址 = f"https://api.music.apple.com/v1/me/library/playlists/{目标歌单ID}/tracks"
                    写入_载荷数据 = {"data": [{"id": 歌曲_内部身份码, "type": "songs"}]}

                    响应_写入结果 = requests.post(写入_接口地址, headers=请求头配置, json=写入_载荷数据)

                    if 响应_写入结果.status_code in (200, 201, 202, 204):
                        return f"✅ 成功入库: {文本_歌名} - {文本_歌手}"
                    else:
                        return f"❌ 写入失败: {文本_歌名} (状态码:{响应_写入结果.status_code})"
                else:
                    return f"🫙 未找到版权: {文本_歌名} - {文本_歌手}"
            else:
                return f"❌ 搜索异常: {文本_歌名} (状态码: {响应_搜索结果.status_code})"

        except Exception as e:
            if 尝试次数 == 最大重试次数 - 1:
                return f"⚠️ 网络异常跳过: {文本_歌名}"
            time.sleep(1)

    return f"❌ 重试失败放弃: {文本_歌名}"


if __name__ == "__main__":
    # ================= 从配置文件加载凭据 =================
    import json
    from pathlib import Path

    _config_path = Path(__file__).resolve().parent.parent / "config.json"
    if not _config_path.exists():
        print(f"❌ 未找到配置文件: {_config_path}")
        print("请复制 config.json 并填写你的 Token 信息。")
        exit(1)

    with open(_config_path, encoding="utf-8") as _f:
        _config = json.load(_f)

    # 1. 酷狗分享链接
    酷狗目标链接 = "https://activity.kugou.com/page/v-3023b6a0/index.html?app=youth&qrcode=https%3A%2F%2Factivity.kugou.com%2Fshare%2Fv-a00a45b0%2Findex.html%3Fu%3D1260607006%26h1%3D25376011111787616395935566045310109492%26h2%3D-%26specialid%3D-2147483648%26global_specialid%3Dcollection_3_1260607006_2_0%26cType%3D0"

    # 2. Apple Music 目标歌单 ID (p.开头)
    苹果目标歌单ID = _config.get("playlist_id", "")
    我的Bearer_Token = _config.get("bearer_token", "")
    我的User_Token = _config.get("user_token", "")

    # ================= 执行引擎 =================

    print("\n" + "=" * 40)
    print("👉 第一阶段：读取酷狗歌单")
    结果_全量歌单 = 提取酷狗虚拟列表歌单(酷狗目标链接)

    if len(结果_全量歌单) == 0:
        print("⚠️ 未获取到酷狗歌曲，程序终止。")
        exit()

    print("\n" + "=" * 40)
    print(f"👉 第二阶段：开启多线程极速转移，共计 {len(结果_全量歌单)} 首")

    # 并发数设为 1，等效单线程，彻底避免限流
    并发数 = 1
    已处理数量 = 0

    with ThreadPoolExecutor(max_workers=并发数) as 线程池:
        任务列表 = []
        for 曲目 in 结果_全量歌单:
            原始歌名 = 曲目["song_name"]
            原始歌手 = 曲目["artist"]
            优化后歌名, 优化后歌手 = 深度清洗文本(原始歌名, 原始歌手)

            任务 = 线程池.submit(向苹果曲库导入单首歌曲, 优化后歌名, 优化后歌手, 我的Bearer_Token, 我的User_Token,
                                 苹果目标歌单ID)
            任务列表.append(任务)

        for 已完成任务 in as_completed(任务列表):
            已处理数量 += 1
            处理结果 = 已完成任务.result()
            print(f"[{已处理数量}/{len(结果_全量歌单)}] {处理结果}")
            # 每首完成后固定间隔 1.2 秒，主动防限流
            time.sleep(1.2)

    print("\n🎉 全自动搬运闭环执行完毕！")