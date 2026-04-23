"""
fetch_videos.py
----------------
Fatih Koparan YouTube kanalındaki tüm videoların meta verilerini çeken script.

Akış:
  1) Root dizindeki .env dosyasından YOUTUBE_API_KEY okunur.
  2) YouTube Data API v3 ile kanalın 'uploads' playlist ID'si bulunur.
  3) Bu playlistteki TÜM videolar sayfalandırma ile çekilir.
  4) Her video için: videoId, title, description, publishedAt, thumbnailUrl toplanır.
  5) Sonuç ../data/raw_videos.json dosyasına yazılır.
"""

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from tqdm import tqdm

# ---------------------------------------------------------------------------
# Sabitler
# ---------------------------------------------------------------------------
CHANNEL_ID = "UCHut-IQXip7mtXyC3GOiQ1A"  # Fatih Koparan
MAX_RESULTS_PER_PAGE = 50  # YouTube API'nin izin verdiği maksimum sayı

# Bu script 'scripts/' klasöründe çalışır.
SCRIPT_DIR = Path(__file__).resolve().parent        # .../scripts
ROOT_DIR = SCRIPT_DIR.parent                         # proje kökü
ENV_PATH = ROOT_DIR / ".env"                         # kökteki .env
DATA_DIR = ROOT_DIR / "data"                         # ../data
OUTPUT_PATH = DATA_DIR / "raw_videos.json"           # ../data/raw_videos.json


def load_api_key() -> str:
    """Root'taki .env dosyasından YOUTUBE_API_KEY'i yükler."""
    if not ENV_PATH.exists():
        sys.exit(f"[HATA] .env dosyası bulunamadı: {ENV_PATH}")

    load_dotenv(dotenv_path=ENV_PATH)
    api_key = os.getenv("YOUTUBE_API_KEY")
    if not api_key:
        sys.exit("[HATA] .env dosyasında YOUTUBE_API_KEY tanımlı değil.")
    return api_key


def get_uploads_playlist_id(youtube, channel_id: str) -> str:
    """Kanalın 'uploads' playlist ID'sini döndürür."""
    response = (
        youtube.channels()
        .list(part="contentDetails,snippet,statistics", id=channel_id)
        .execute()
    )

    items = response.get("items", [])
    if not items:
        sys.exit(f"[HATA] Kanal bulunamadı: {channel_id}")

    uploads_id = items[0]["contentDetails"]["relatedPlaylists"]["uploads"]
    channel_title = items[0]["snippet"]["title"]
    video_count = items[0].get("statistics", {}).get("videoCount", "bilinmiyor")

    print(f"[BILGI] Kanal: {channel_title}")
    print(f"[BILGI] Toplam video (API): {video_count}")
    print(f"[BILGI] Uploads Playlist ID: {uploads_id}")

    return uploads_id, int(video_count) if str(video_count).isdigit() else None


def pick_best_thumbnail(thumbnails: dict) -> str:
    """En yüksek kaliteli thumbnail URL'sini seçer."""
    # YouTube öncelik sırası (yüksekten düşüğe)
    priority = ["maxres", "standard", "high", "medium", "default"]
    for key in priority:
        if key in thumbnails and thumbnails[key].get("url"):
            return thumbnails[key]["url"]
    return ""


def fetch_all_videos(youtube, uploads_playlist_id: str, total_videos: int | None):
    """playlistItems endpoint'i ile tüm videoları sayfalandırarak çeker."""
    videos = []
    next_page_token = None

    # tqdm için toplam biliniyorsa kullan, yoksa bilinmeden ilerle
    progress = tqdm(
        total=total_videos,
        desc="Videolar çekiliyor",
        unit="video",
        ncols=100,
    )

    try:
        while True:
            response = (
                youtube.playlistItems()
                .list(
                    part="snippet,contentDetails",
                    playlistId=uploads_playlist_id,
                    maxResults=MAX_RESULTS_PER_PAGE,
                    pageToken=next_page_token,
                )
                .execute()
            )

            for item in response.get("items", []):
                snippet = item.get("snippet", {})
                content_details = item.get("contentDetails", {})

                video_id = content_details.get("videoId") or snippet.get(
                    "resourceId", {}
                ).get("videoId")

                if not video_id:
                    continue

                videos.append(
                    {
                        "videoId": video_id,
                        "title": snippet.get("title", ""),
                        "description": snippet.get("description", ""),
                        "publishedAt": content_details.get("videoPublishedAt")
                        or snippet.get("publishedAt", ""),
                        "thumbnailUrl": pick_best_thumbnail(
                            snippet.get("thumbnails", {})
                        ),
                    }
                )
                progress.update(1)

            next_page_token = response.get("nextPageToken")
            if not next_page_token:
                break
    finally:
        progress.close()

    return videos


def save_videos(videos: list, output_path: Path) -> None:
    """Videoları JSON olarak kaydeder."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(videos, f, ensure_ascii=False, indent=2)
    print(f"[OK] {len(videos)} video kaydedildi -> {output_path}")


def main() -> None:
    api_key = load_api_key()

    try:
        youtube = build("youtube", "v3", developerKey=api_key)

        uploads_playlist_id, video_count = get_uploads_playlist_id(
            youtube, CHANNEL_ID
        )

        videos = fetch_all_videos(youtube, uploads_playlist_id, video_count)
        save_videos(videos, OUTPUT_PATH)

    except HttpError as e:
        sys.exit(f"[HATA] YouTube API isteği başarısız: {e}")
    except Exception as e:
        sys.exit(f"[HATA] Beklenmeyen bir hata oluştu: {e}")


if __name__ == "__main__":
    main()
