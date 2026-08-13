#!/usr/bin/env python3
"""One-time, preview-first NetEase playlist importer for Apple Music.

The script reads a NetEase playlist, matches tracks against the Apple Music
catalog for the signed-in account's storefront, writes a local report, and
creates a new Apple Music playlist only after explicit confirmation.
"""

from __future__ import annotations

import argparse
import base64
import csv
import getpass
import json
import os
import re
import sys
import time
import unicodedata
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import requests
from opencc import OpenCC

from 导入applemusic.pyncm.pyncm import GetCurrentSession, apis

APPLE_API_BASE = "https://api.music.apple.com"
APPLE_WEB_BASE = "https://music.apple.com"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136 Safari/537.36"
)
DEFAULT_AUTO_SCORE = 82.0
DEFAULT_REVIEW_SCORE = 68.0
REPORT_DIR = Path(__file__).resolve().parent / "reports"
OPENCC_T2S = OpenCC("t2s")

VERSION_MARKERS = {
    "live": {"live", "现场", "ライブ"},
    "instrumental": {"instrumental", "伴奏", "纯音乐", "インスト"},
    "karaoke": {"karaoke", "卡拉ok", "カラオケ"},
    "remix": {"remix", "混音", "リミックス"},
    "acoustic": {"acoustic", "不插电", "アコースティック"},
    "cover": {"cover", "翻唱", "カバー"},
}


class MigrationError(RuntimeError):
    """A user-facing migration failure."""


@dataclass(frozen=True)
class SourceTrack:
    id: str
    name: str
    artists: tuple[str, ...]
    album: str
    duration_ms: int

    @property
    def display_artist(self) -> str:
        return " / ".join(self.artists)


@dataclass(frozen=True)
class CatalogMatch:
    id: str
    name: str
    artist: str
    album: str
    duration_ms: int
    url: str
    score: float
    status: str
    query: str


def parse_playlist_id(value: str) -> str:
    """Accept a numeric ID, a NetEase URL, or copied share text."""
    value = value.strip()
    if value.isdigit():
        return value
    patterns = (
        r"(?:playlist\?|[?&#])id=(\d+)",
        r"music\.163\.com/(?:m/)?playlist/(\d+)",
    )
    for pattern in patterns:
        match = re.search(pattern, value, flags=re.IGNORECASE)
        if match:
            return match.group(1)
    raise MigrationError("无法从输入内容中识别网易云歌单 ID")


def normalize_text(value: str) -> str:
    value = OPENCC_T2S.convert(unicodedata.normalize("NFKC", value or "")).lower()
    value = value.replace("＆", "&")
    value = re.sub(r"\b(feat|featuring|ft)\.?\b.*$", "", value)
    value = re.sub(r"[\s\-‐‑‒–—_/·・.,!?;:'\"“”‘’()（）\[\]【】]+", "", value)
    return value.strip()


def text_similarity(left: str, right: str) -> float:
    left_n = normalize_text(left)
    right_n = normalize_text(right)
    if not left_n or not right_n:
        return 0.0
    if left_n == right_n:
        return 1.0
    return SequenceMatcher(None, left_n, right_n).ratio()


def detected_versions(value: str) -> set[str]:
    normalized = unicodedata.normalize("NFKC", value or "").lower()
    found: set[str] = set()
    for version, markers in VERSION_MARKERS.items():
        if any(marker in normalized for marker in markers):
            found.add(version)
    return found


def score_candidate(source: SourceTrack, candidate: dict[str, Any]) -> float:
    attrs = candidate.get("attributes") or {}
    candidate_name = str(attrs.get("name") or "")
    candidate_artist = str(attrs.get("artistName") or "")
    candidate_album = str(attrs.get("albumName") or "")
    candidate_duration = int(attrs.get("durationInMillis") or 0)

    title_score = text_similarity(source.name, candidate_name)
    artist_score = max(
        (text_similarity(artist, candidate_artist) for artist in source.artists),
        default=0.0,
    )
    album_score = text_similarity(source.album, candidate_album)

    duration_score = 0.0
    if source.duration_ms and candidate_duration:
        difference = abs(source.duration_ms - candidate_duration)
        if difference <= 2_500:
            duration_score = 1.0
        elif difference <= 6_000:
            duration_score = 0.65
        elif difference <= 12_000:
            duration_score = 0.25

    score = title_score * 55 + artist_score * 30 + album_score * 8 + duration_score * 7

    if title_score < 0.55:
        score -= 25
    strong_localized_identity = (
        title_score >= 0.95 and album_score >= 0.90 and duration_score >= 0.65
    )
    if strong_localized_identity and artist_score < 0.45:
        # Apple storefronts frequently localize artist names (for example,
        # 告五人 -> Accusefive). Exact title + album + duration is a stronger
        # identity signal than the localized artist display name.
        score += 15
    elif source.artists and artist_score < 0.45:
        score -= 22

    source_versions = detected_versions(f"{source.name} {source.album}")
    candidate_versions = detected_versions(f"{candidate_name} {candidate_album}")
    if source_versions != candidate_versions:
        score -= 18 * len(source_versions.symmetric_difference(candidate_versions))

    return round(max(0.0, min(100.0, score)), 2)


def classify_score(score: float, auto_score: float, review_score: float) -> str:
    if score >= auto_score:
        return "matched"
    if score >= review_score:
        return "needs_review"
    return "unmatched"


def chunks(values: list[str], size: int) -> Iterable[list[str]]:
    for index in range(0, len(values), size):
        yield values[index : index + size]


def configure_netease_session() -> None:
    music_u = os.environ.get("NETEASE_MUSIC_U", "").strip()
    if music_u:
        apis.login.LoginViaCookie(music_u)
    session = GetCurrentSession()
    session.headers["X-Real-IP"] = "118.88.88.88"


def load_netease_playlist(playlist_id: str) -> tuple[str, list[SourceTrack]]:
    configure_netease_session()
    detail = apis.playlist.GetPlaylistInfo(int(playlist_id))
    playlist = detail.get("playlist") if isinstance(detail, dict) else None
    if not isinstance(playlist, dict):
        raise MigrationError(f"网易云没有返回有效歌单：{str(detail)[:300]}")

    playlist_name = str(playlist.get("name") or f"网易云歌单-{playlist_id}")
    ordered_ids = [str(item.get("id")) for item in playlist.get("trackIds") or []]
    ordered_ids = [item for item in ordered_ids if item and item != "None"]
    if not ordered_ids:
        raise MigrationError(
            "歌单没有可读取的曲目。若这是私密的“我喜欢的音乐”，请设置 NETEASE_MUSIC_U 后重试。"
        )

    songs_by_id: dict[str, dict[str, Any]] = {
        str(song.get("id")): song
        for song in playlist.get("tracks") or []
        if song.get("id") is not None
    }
    missing_ids = [track_id for track_id in ordered_ids if track_id not in songs_by_id]
    for batch in chunks(missing_ids, 500):
        response = apis.track.GetTrackDetail([int(track_id) for track_id in batch])
        for song in response.get("songs") or []:
            songs_by_id[str(song.get("id"))] = song

    tracks: list[SourceTrack] = []
    for track_id in ordered_ids:
        song = songs_by_id.get(track_id)
        if not song:
            continue
        artists = tuple(
            str(artist.get("name") or "").strip()
            for artist in song.get("ar") or song.get("artists") or []
            if str(artist.get("name") or "").strip()
        )
        album = song.get("al") or song.get("album") or {}
        tracks.append(
            SourceTrack(
                id=track_id,
                name=str(song.get("name") or "").strip(),
                artists=artists,
                album=str(album.get("name") or "").strip()
                if isinstance(album, dict)
                else "",
                duration_ms=int(song.get("dt") or song.get("duration") or 0),
            )
        )
    if not tracks:
        raise MigrationError("已找到歌单，但没有取得任何完整曲目信息")
    return playlist_name, tracks


def decode_jwt_payload(token: str) -> dict[str, Any]:
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        return json.loads(base64.urlsafe_b64decode(payload).decode("utf-8"))
    except (IndexError, ValueError, json.JSONDecodeError) as exc:
        raise MigrationError("Apple developer token 格式无效") from exc


def fetch_apple_developer_token(session: requests.Session) -> str:
    supplied = os.environ.get("APPLE_MUSIC_DEVELOPER_TOKEN", "").strip()
    if supplied:
        return supplied

    response = session.get(
        f"{APPLE_WEB_BASE}/us/browse",
        headers={"User-Agent": USER_AGENT},
        timeout=30,
    )
    response.raise_for_status()
    html = response.text
    asset_urls = list(
        dict.fromkeys(
            urljoin(APPLE_WEB_BASE, value)
            for value in re.findall(
                r"(?:src|href)=[\"']([^\"']+\.js(?:\?[^\"']*)?)[\"']", html
            )
        )
    )
    jwt_pattern = re.compile(
        r"eyJ[a-zA-Z0-9_-]{15,}\.eyJ[a-zA-Z0-9_-]{15,}\.[a-zA-Z0-9_-]{15,}"
    )
    for asset_url in asset_urls:
        try:
            asset = session.get(
                asset_url, headers={"User-Agent": USER_AGENT}, timeout=30
            )
            asset.raise_for_status()
        except requests.RequestException:
            continue
        for token in jwt_pattern.findall(asset.text):
            try:
                payload = decode_jwt_payload(token)
            except MigrationError:
                continue
            if payload.get("iss") != "AMPWebPlay":
                continue
            if int(payload.get("exp") or 0) <= int(time.time()):
                continue
            return token
    raise MigrationError(
        "无法自动取得 Apple developer token。可临时设置 APPLE_MUSIC_DEVELOPER_TOKEN 后重试。"
    )


class AppleMusicClient:
    def __init__(
        self, developer_token: str, user_token: str, *, interval: float = 0.65
    ):
        self.session = requests.Session()
        self.developer_token = developer_token
        self.user_token = user_token
        self.storefront = ""
        self.interval = max(0.2, interval)
        self.last_request_at = 0.0

    @property
    def headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.developer_token}",
            "Music-User-Token": self.user_token,
            "Content-Type": "application/json",
            "Origin": APPLE_WEB_BASE,
            "Referer": f"{APPLE_WEB_BASE}/",
            "User-Agent": USER_AGENT,
        }

    def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str] | None = None,
        body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        for attempt in range(6):
            elapsed = time.monotonic() - self.last_request_at
            if elapsed < self.interval:
                time.sleep(self.interval - elapsed)
            response = self.session.request(
                method,
                f"{APPLE_API_BASE}{path}",
                headers=self.headers,
                params=params,
                json=body,
                timeout=40,
            )
            self.last_request_at = time.monotonic()
            if response.status_code == 429 or response.status_code >= 500:
                if attempt == 5:
                    break
                retry_after = response.headers.get("Retry-After", "")
                try:
                    wait = max(1.0, float(retry_after))
                except ValueError:
                    wait = min(30.0, 2.0**attempt)
                time.sleep(wait)
                continue
            if response.status_code not in {200, 201, 202, 204}:
                detail = response.text[:500]
                raise MigrationError(
                    f"Apple Music API {response.status_code}: {detail}"
                )
            if not response.content:
                return {}
            return response.json()
        raise MigrationError(f"Apple Music API 多次重试仍失败：{path}")

    def detect_storefront(self, override: str = "") -> str:
        data = self.request("GET", "/v1/me/storefront")
        detected = str((data.get("data") or [{}])[0].get("id") or "").lower()
        if not detected:
            raise MigrationError("Apple Music 没有返回账号 storefront")
        if override and override.lower() != detected:
            print(
                f"注意：账号 storefront 为 {detected}，按参数改用 {override.lower()} 搜索。"
            )
            self.storefront = override.lower()
        else:
            self.storefront = detected
        return self.storefront

    def search_songs(self, term: str, limit: int = 10) -> list[dict[str, Any]]:
        if not self.storefront:
            raise MigrationError("必须先检测 Apple Music storefront")
        data = self.request(
            "GET",
            f"/v1/catalog/{self.storefront}/search",
            params={"term": term, "types": "songs", "limit": str(limit)},
        )
        return list(data.get("results", {}).get("songs", {}).get("data") or [])

    def create_playlist(self, name: str, description: str) -> str:
        data = self.request(
            "POST",
            "/v1/me/library/playlists",
            body={"attributes": {"name": name, "description": description}},
        )
        playlist_id = str((data.get("data") or [{}])[0].get("id") or "")
        if not playlist_id:
            raise MigrationError("Apple Music 已响应创建请求，但没有返回歌单 ID")
        return playlist_id

    def add_tracks(self, playlist_id: str, track_ids: list[str]) -> None:
        for index, batch in enumerate(chunks(track_ids, 25), 1):
            self.request(
                "POST",
                f"/v1/me/library/playlists/{playlist_id}/tracks",
                body={
                    "data": [{"id": track_id, "type": "songs"} for track_id in batch]
                },
            )
            print(f"  已写入 {min(index * 25, len(track_ids))}/{len(track_ids)} 首")

    def count_playlist_tracks(self, playlist_id: str) -> int:
        total = 0
        path = f"/v1/me/library/playlists/{playlist_id}/tracks"
        params: dict[str, str] | None = {"limit": "100"}
        while path:
            data = self.request("GET", path, params=params)
            params = None
            total += len(data.get("data") or [])
            next_path = str(data.get("next") or "")
            path = next_path.replace(APPLE_API_BASE, "") if next_path else ""
        return total


def best_catalog_match(
    client: AppleMusicClient,
    source: SourceTrack,
    *,
    auto_score: float,
    review_score: float,
) -> CatalogMatch | None:
    primary_artist = source.artists[0] if source.artists else ""
    queries = list(
        dict.fromkeys(
            value.strip()
            for value in (
                f"{source.name} {primary_artist}",
                f"{source.name} {source.album}",
                source.name,
            )
            if value.strip()
        )
    )
    best: tuple[float, dict[str, Any], str] | None = None
    seen_ids: set[str] = set()
    for query in queries:
        for candidate in client.search_songs(query, limit=10):
            candidate_id = str(candidate.get("id") or "")
            if not candidate_id or candidate_id in seen_ids:
                continue
            seen_ids.add(candidate_id)
            score = score_candidate(source, candidate)
            if best is None or score > best[0]:
                best = (score, candidate, query)
        if best and best[0] >= auto_score:
            break
    if not best:
        return None

    score, candidate, query = best
    attrs = candidate.get("attributes") or {}
    status = classify_score(score, auto_score, review_score)
    return CatalogMatch(
        id=str(candidate.get("id") or ""),
        name=str(attrs.get("name") or ""),
        artist=str(attrs.get("artistName") or ""),
        album=str(attrs.get("albumName") or ""),
        duration_ms=int(attrs.get("durationInMillis") or 0),
        url=str(attrs.get("url") or ""),
        score=score,
        status=status,
        query=query,
    )


def get_user_token() -> str:
    token = os.environ.get("APPLE_MUSIC_USER_TOKEN", "").strip()
    if token:
        return token
    token = getpass.getpass(
        "请输入 music.apple.com 的 media-user-token（输入不会显示）："
    ).strip()
    if not token:
        raise MigrationError("未提供 Apple Music media-user-token")
    return token


def match_tracks(
    client: AppleMusicClient,
    tracks: list[SourceTrack],
    *,
    auto_score: float,
    review_score: float,
    limit: int,
) -> list[dict[str, Any]]:
    selected = tracks[:limit] if limit else tracks
    results: list[dict[str, Any]] = []
    for index, track in enumerate(selected, 1):
        print(f"[{index}/{len(selected)}] 匹配：{track.name} — {track.display_artist}")
        try:
            match = best_catalog_match(
                client,
                track,
                auto_score=auto_score,
                review_score=review_score,
            )
            error = ""
        except MigrationError as exc:
            match = None
            error = str(exc)
        row = {
            "source": {
                **asdict(track),
                "artists": list(track.artists),
            },
            "match": asdict(match) if match else None,
            "status": match.status if match else "error" if error else "unmatched",
            "error": error,
        }
        results.append(row)
        if match:
            print(
                f"  → {match.status} {match.score:.1f}: {match.name} — {match.artist}"
            )
        else:
            print(f"  → {'错误: ' + error if error else '未匹配'}")
    return results


def unique_track_ids(results: list[dict[str, Any]], include_review: bool) -> list[str]:
    allowed = {"matched"}
    if include_review:
        allowed.add("needs_review")
    output: list[str] = []
    seen: set[str] = set()
    for row in results:
        match = row.get("match") or {}
        track_id = str(match.get("id") or "")
        if row.get("status") not in allowed or not track_id or track_id in seen:
            continue
        seen.add(track_id)
        output.append(track_id)
    return output


def write_reports(payload: dict[str, Any]) -> tuple[Path, Path]:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    json_path = REPORT_DIR / f"migration-{stamp}.json"
    csv_path = REPORT_DIR / f"migration-{stamp}.csv"
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    with csv_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(
            [
                "status",
                "score",
                "netease_name",
                "netease_artist",
                "netease_album",
                "apple_name",
                "apple_artist",
                "apple_album",
                "apple_url",
                "error",
            ]
        )
        for row in payload["results"]:
            source = row.get("source") or {}
            match = row.get("match") or {}
            writer.writerow(
                [
                    row.get("status"),
                    match.get("score", ""),
                    source.get("name", ""),
                    " / ".join(source.get("artists") or []),
                    source.get("album", ""),
                    match.get("name", ""),
                    match.get("artist", ""),
                    match.get("album", ""),
                    match.get("url", ""),
                    row.get("error", ""),
                ]
            )
    return json_path, csv_path


def summary(results: list[dict[str, Any]]) -> dict[str, int]:
    statuses = {"matched": 0, "needs_review": 0, "unmatched": 0, "error": 0}
    for row in results:
        status = str(row.get("status"))
        statuses[status] = statuses.get(status, 0) + 1
    return statuses


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="将网易云歌单一次性、预览后导入外区 Apple Music",
    )
    parser.add_argument("source", help="网易云歌单 ID、链接或包含链接的分享文本")
    parser.add_argument("--target-name", help="新建的 Apple Music 歌单名称")
    parser.add_argument("--storefront", help="覆盖自动检测结果，例如 us、jp、hk")
    parser.add_argument("--auto-score", type=float, default=DEFAULT_AUTO_SCORE)
    parser.add_argument("--review-score", type=float, default=DEFAULT_REVIEW_SCORE)
    parser.add_argument(
        "--include-review", action="store_true", help="同时导入需要人工复核的匹配"
    )
    parser.add_argument(
        "--limit", type=int, default=0, help="仅处理前 N 首，适合先做小规模测试"
    )
    parser.add_argument(
        "--commit", action="store_true", help="预览后允许创建并写入 Apple Music 歌单"
    )
    parser.add_argument(
        "--yes", action="store_true", help="与 --commit 一起使用，跳过最终手工确认"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.review_score > args.auto_score:
        raise MigrationError("--review-score 不能高于 --auto-score")
    if args.limit < 0:
        raise MigrationError("--limit 不能为负数")

    playlist_id = parse_playlist_id(args.source)
    print(f"读取网易云歌单 {playlist_id}…")
    playlist_name, tracks = load_netease_playlist(playlist_id)
    if args.limit:
        print(f"已读取 {len(tracks)} 首，本次只处理前 {args.limit} 首。")
    else:
        print(f"已读取「{playlist_name}」共 {len(tracks)} 首。")

    web_session = requests.Session()
    developer_token = fetch_apple_developer_token(web_session)
    client = AppleMusicClient(developer_token, get_user_token())
    storefront = client.detect_storefront(args.storefront or "")
    print(f"Apple Music storefront：{storefront}")

    results = match_tracks(
        client,
        tracks,
        auto_score=args.auto_score,
        review_score=args.review_score,
        limit=args.limit,
    )
    stats = summary(results)
    target_name = args.target_name or f"{playlist_name}（网易云导入）"
    payload: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": {"playlist_id": playlist_id, "playlist_name": playlist_name},
        "apple_music": {"storefront": storefront, "target_name": target_name},
        "options": {
            "auto_score": args.auto_score,
            "review_score": args.review_score,
            "include_review": args.include_review,
            "limit": args.limit,
        },
        "summary": stats,
        "results": results,
        "write_result": None,
    }
    json_path, csv_path = write_reports(payload)

    print("\n预览完成：")
    print(f"  自动匹配：{stats.get('matched', 0)}")
    print(f"  需要复核：{stats.get('needs_review', 0)}")
    print(f"  未匹配：{stats.get('unmatched', 0)}")
    print(f"  错误：{stats.get('error', 0)}")
    print(f"  JSON 报告：{json_path}")
    print(f"  CSV 报告：{csv_path}")

    track_ids = unique_track_ids(results, args.include_review)
    if not args.commit:
        print("\n当前是默认预览模式，Apple Music 未发生任何修改。")
        print("检查报告后，在原命令末尾增加 --commit 才会创建新歌单。")
        return 0
    if not track_ids:
        raise MigrationError("没有达到导入标准的曲目，未创建 Apple Music 歌单")

    if not args.yes:
        phrase = f"IMPORT {len(track_ids)}"
        answer = input(
            f"\n将新建「{target_name}」并写入 {len(track_ids)} 首。请输入 {phrase} 继续："
        )
        if answer.strip() != phrase:
            print("确认内容不匹配，已取消；Apple Music 未发生修改。")
            return 0

    playlist_description = (
        f"从网易云「{playlist_name}」一次性导入；"
        f"storefront={storefront}；"
        f"生成时间={datetime.now(timezone.utc).isoformat(timespec='seconds')}"
    )
    apple_playlist_id = client.create_playlist(target_name, playlist_description)
    print(f"已创建 Apple Music 歌单：{apple_playlist_id}")
    try:
        client.add_tracks(apple_playlist_id, track_ids)
        verified_count = client.count_playlist_tracks(apple_playlist_id)
    except Exception as exc:
        payload["write_result"] = {
            "playlist_id": apple_playlist_id,
            "requested_tracks": len(track_ids),
            "status": "partial_or_unknown",
            "error": str(exc),
        }
        write_reports(payload)
        raise MigrationError(
            f"歌单已创建，但写入或验证中断。请先检查 Apple Music 歌单 {apple_playlist_id}：{exc}"
        ) from exc

    payload["write_result"] = {
        "playlist_id": apple_playlist_id,
        "requested_tracks": len(track_ids),
        "verified_tracks": verified_count,
        "status": "verified" if verified_count == len(track_ids) else "count_mismatch",
    }
    json_path, csv_path = write_reports(payload)
    print(f"完成：请求写入 {len(track_ids)} 首，Apple Music 读回 {verified_count} 首。")
    print(f"最终报告：{json_path}")
    return 0 if verified_count == len(track_ids) else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (MigrationError, requests.RequestException) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        raise SystemExit(1)
