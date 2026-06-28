import time
import re
import json
import random
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
# 🌟 引入网易云解密客户端组件
from 导入applemusic.pyncm.pyncm import apis

# ================= 核心防御架构 =================
# 🌟 建立一个全局的长连接池，所有线程共用这一条“秘密通道”
# 极大降低由于频繁握手导致的苹果 WAF 防火墙断连 (ConnectionResetError)
苹果_全局通道 = requests.Session()


def 提取网易云歌单(歌单ID):
    """
    模块一：利用 pyncm 伪装客户端，秒级秒杀全量歌单数据
    """
    print(f"🚀 正在调用底层解密协议，越过网页限制请求网易云核心 API (目标 ID: {歌单ID})...")
    try:
        响应数据 = apis.playlist.GetPlaylistInfo(歌单ID)
        歌曲详情列表 = 响应数据['playlist']['tracks']

        print(f"✅ 成功破解网易云加密防御！全量触达：共计 {len(歌曲详情列表)} 首歌曲。")

        完整播放列表 = []
        for 歌曲 in 歌曲详情列表:
            歌名 = 歌曲['name']
            歌手 = 歌曲['ar'][0]['name'] if 歌曲['ar'] else "未知歌手"
            完整播放列表.append({"song_name": 歌名, "artist": 歌手})

        return 完整播放列表
    except Exception as 错误对象:
        print(f"❌ 提取网易云数据流失败: {错误对象}")
        return []


def 深度清洗文本(歌名, 歌手):
    """
    模块二：正则表达式数据净化洗涤器
    """
    干净_歌名 = re.sub(r'\(.*?\)|（.*?）|\[.*?\]|【.*?】', '', 歌名).strip()
    干净_歌手 = re.split(r'[/&]', 歌手)[0].strip()
    return 干净_歌名, 干净_歌手


def 向苹果曲库导入单首歌曲(原始歌名, 原始歌手, 净化歌名, 净化歌手, 开发者临时凭证, 用户授权凭证, 目标歌单ID):
    """
    模块三：苹果音乐 API 调用写入 (长连接 + 指数退避 + 结构化返回)
    """
    请求头配置 = {
        "Authorization": f"Bearer {开发者临时凭证}",
        "music-user-token": 用户授权凭证,
        "Origin": "https://music.apple.com",
        "Content-Type": "application/json"
    }

    搜索_基础接口 = "https://api.music.apple.com/v1/catalog/cn/search"
    请求_网址 = f"{搜索_基础接口}?term={净化歌名} {净化歌手}&types=songs&limit=1"

    # 失败记录的通用模板
    失败记录 = {
        "original_song_name": 原始歌名,
        "original_artist": 原始歌手,
        "search_term": f"{净化歌名} {净化歌手}",
        "reason": "未知错误"
    }

    最大重试次数 = 15

    for 尝试次数 in range(最大重试次数):
        try:
            # 🌟 统一使用 苹果_全局通道 进行网络请求
            响应_搜索结果 = 苹果_全局通道.get(请求_网址, headers=请求头配置, timeout=15)

            # 429 限流保护
            if 响应_搜索结果.status_code == 429:
                等待时间 = (2 ** 尝试次数) + random.uniform(0.5, 1.5)
                print(f"⚠️ [触发限流] 苹果要求减速！《{净化歌名}》原地休眠 {等待时间:.1f} 秒后再次死磕...")
                time.sleep(等待时间)
                continue

            if 响应_搜索结果.status_code == 200:
                解析_数据字典 = 响应_搜索结果.json()

                # 检查版权是否存在
                if "songs" in 解析_数据字典["results"] and len(解析_数据字典["results"]["songs"]["data"]) > 0:
                    歌曲_内部身份码 = 解析_数据字典["results"]["songs"]["data"][0]["id"]

                    写入_接口地址 = f"https://api.music.apple.com/v1/me/library/playlists/{目标歌单ID}/tracks"
                    写入_载荷数据 = {"data": [{"id": 歌曲_内部身份码, "type": "songs"}]}

                    响应_写入结果 = 苹果_全局通道.post(写入_接口地址, headers=请求头配置, json=写入_载荷数据,
                                                       timeout=15)

                    if 响应_写入结果.status_code in (200, 201, 202, 204):
                        return {"status": "success", "msg": f"✅ 成功入库: {净化歌名} - {净化歌手}"}
                    else:
                        失败记录["reason"] = f"写入接口报错 (状态码:{响应_写入结果.status_code})"
                        return {"status": "fail", "data": 失败记录,
                                "msg": f"❌ 写入失败: {净化歌名} (状态码:{响应_写入结果.status_code})"}
                else:
                    失败记录["reason"] = "Apple Music 中国区未找到对应版权"
                    return {"status": "fail", "data": 失败记录, "msg": f"🫙 未找到版权: {净化歌名} - {净化歌手}"}
            else:
                失败记录["reason"] = f"搜索接口异常 (状态码:{响应_搜索结果.status_code})"
                return {"status": "fail", "data": 失败记录,
                        "msg": f"❌ 搜索异常: {净化歌名} (状态码: {响应_搜索结果.status_code})"}

        except Exception as e:
            等待时间 = (2 ** 尝试次数) + 2
            print(f"📡 [网络波动/防火墙] 《{净化歌名}》连接异常断开，{等待时间:.1f}秒后重试...")
            time.sleep(等待时间)

    失败记录["reason"] = "达到最大死磕重试上限，疑似遭遇持续网络封锁"
    return {"status": "fail", "data": 失败记录, "msg": f"❌ 彻底死磕失败，无奈跳过: {净化歌名}"}


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

    网易云歌单ID = 6608947267
    苹果目标歌单ID = _config.get("playlist_id", "")
    我的Bearer_Token = _config.get("bearer_token", "")
    我的User_Token = _config.get("user_token", "")

    # ================= 自动化执行链路 =================

    print("\n" + "=" * 50)
    print("🎯 第一阶段：同步数据网关")
    待转移全量列表 = 提取网易云歌单(网易云歌单ID)

    if not 待转移全量列表:
        print("⚠️ 未能在网易云内解析到数据，程序安全退出。")
        exit()

    print("\n" + "=" * 50)
    print(f"🎯 第二阶段：启动高并发异步流（分配工作线程：4，目标总量：{len(待转移全量列表)}）")

    # 🌟 既然用了复用长连接，4 个并发足以跑满带宽且最安全
    并发限制数 = 1
    累计已处理 = 0
    所有失败记录 = []  # 用于收集失败日志的空列表

    with ThreadPoolExecutor(max_workers=并发限制数) as 线程池:
        异步任务映射 = []
        for 歌曲项 in 待转移全量列表:
            原始名 = 歌曲项["song_name"]
            原始人 = 歌曲项["artist"]
            干净名, 干净人 = 深度清洗文本(原始名, 原始人)

            任务句柄 = 线程池.submit(
                向苹果曲库导入单首歌曲,
                原始名, 原始人, 干净名, 干净人,  # 把原始名字也传进去，方便日志记录
                我的Bearer_Token, 我的User_Token, 苹果目标歌单ID
            )
            异步任务映射.append(任务句柄)

        # 回调收集器：监听并分类处理结果
        for 完成的任务 in as_completed(异步任务映射):
            累计已处理 += 1
            线程返回结果 = 完成的任务.result()
            print(f"[{累计已处理}/{len(待转移全量列表)}] {线程返回结果['msg']}")

            # 如果判定为失败，将其塞入失败清单
            if 线程返回结果['status'] == 'fail':
                所有失败记录.append(线程返回结果['data'])

    # ================= 阶段三：战损清点与 JSON 落地 =================
    print("\n" + "=" * 50)
    if len(所有失败记录) > 0:
        json_文件路径 = f"未成功导入名单_{int(time.time())}.json"

        # 将失败记录写入本地 JSON 文件
        with open(json_文件路径, 'w', encoding='utf-8') as f:
            json.dump(所有失败记录, f, ensure_ascii=False, indent=4)

        print(f"⚠️ 迁移结束！成功导入 {len(待转移全量列表) - len(所有失败记录)} 首。")
        print(f"📂 有 {len(所有失败记录)} 首歌未能成功导入，详情已生成至当前目录：【{json_文件路径}】")
    else:
        print("🎉 【完美闭环大获全胜】 389 首网易云音乐全部 100% 成功导入，毫无遗漏！")