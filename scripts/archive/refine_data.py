# =============================================================================
# refine_data.py
# -----------------------------------------------------------------------------
# KURULUM (ÖNEMLİ):
#     pip install google-api-python-client python-dotenv tqdm
# =============================================================================
"""
'data/raw_videos.json' içindeki videoların sürelerini YouTube Data API v3 ile
çeker, 60 saniye ve altındaki videoları (Shorts) eler, kalanları Gemini'den
üretilen 'data/locations.json' dosyasındaki konum bilgileriyle videoId üzerinden
birleştirir ve hem süresi > 60sn hem de 'country' bilgisi 'Unknown' OLMAYAN
videoları 'data/final_refined_data.json' dosyasına kaydeder.

Çıktı formatı (her obje):
    {
        "videoId": "...",
        "title": "...",
        "publishedAt": "...",
        "thumbnailUrl": "...",
        "city": "...",
        "country": "...",
        "duration_seconds": 123
    }
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from tqdm import tqdm

try:
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
except ImportError:
    sys.exit(
        "[HATA] 'google-api-python-client' kütüphanesi yüklü değil.\n"
        "       Kurulum: pip install google-api-python-client"
    )

# =============================================================================
# Yol sabitleri
# =============================================================================
SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent
ENV_PATH = ROOT_DIR / ".env"
DATA_DIR = ROOT_DIR / "data"
RAW_VIDEOS_PATH = DATA_DIR / "raw_videos.json"
LOCATIONS_PATH = DATA_DIR / "locations.json"
OUTPUT_PATH = DATA_DIR / "final_refined_data.json"

# =============================================================================
# Sabitler
# =============================================================================
BATCH_SIZE = 50            # youtube.videos().list API sınırı
SHORTS_THRESHOLD_SEC = 60  # bu saniyenin ALTI (dahil) Shorts sayılır

# ISO 8601 duration regex'i (YouTube formatları: PT1H2M3S, PT45M, PT30S, PT1M, vs.)
DURATION_RE = re.compile(
    r"^P"
    r"(?:(?P<days>\d+)D)?"
    r"(?:T"
    r"(?:(?P<hours>\d+)H)?"
    r"(?:(?P<minutes>\d+)M)?"
    r"(?:(?P<seconds>\d+)S)?"
    r")?$"
)


def parse_duration_to_seconds(duration: str) -> int:
    """ISO 8601 duration string'ini toplam saniyeye çevirir."""
    if not duration:
        return 0

    m = DURATION_RE.match(duration.strip())
    if not m:
        return 0

    days = int(m.group("days") or 0)
    hours = int(m.group("hours") or 0)
    minutes = int(m.group("minutes") or 0)
    seconds = int(m.group("seconds") or 0)

    return days * 86400 + hours * 3600 + minutes * 60 + seconds


# =============================================================================
# Yardımcılar
# =============================================================================
def load_api_key() -> str:
    if not ENV_PATH.exists():
        sys.exit(f"[HATA] .env dosyası bulunamadı: {ENV_PATH}")

    load_dotenv(dotenv_path=ENV_PATH)
    api_key = os.getenv("YOUTUBE_API_KEY")
    if not api_key:
        sys.exit("[HATA] .env dosyasında YOUTUBE_API_KEY tanımlı değil.")
    return api_key


def load_json(path: Path, default: Any):
    if not path.exists():
        sys.exit(f"[HATA] Dosya bulunamadı: {path}")
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        sys.exit(f"[HATA] {path} parse edilemedi: {e}")


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp_path.replace(path)


# =============================================================================
# YouTube API — 50'lik batch ile süre çekme
# =============================================================================
def fetch_durations(youtube, video_ids: list[str]) -> dict[str, int]:
    """
    Verilen videoId listesi için {videoId: duration_seconds} sözlüğü döner.
    50'şerli gruplar halinde çağrı yapar, tqdm ile ilerleme gösterir.
    """
    durations: dict[str, int] = {}
    total_batches = (len(video_ids) + BATCH_SIZE - 1) // BATCH_SIZE

    pbar = tqdm(total=total_batches, unit="batch", ncols=100)

    for batch_index in range(total_batches):
        start = batch_index * BATCH_SIZE
        batch_ids = video_ids[start : start + BATCH_SIZE]
        pbar.set_description(f"Batch {batch_index + 1}/{total_batches} süreler çekiliyor")

        try:
            response = (
                youtube.videos()
                .list(part="contentDetails", id=",".join(batch_ids))
                .execute()
            )
        except HttpError as e:
            pbar.close()
            sys.exit(f"[HATA] YouTube API isteği başarısız: {e}")

        for item in response.get("items", []):
            vid = item.get("id")
            duration_iso = item.get("contentDetails", {}).get("duration", "")
            if vid:
                durations[vid] = parse_duration_to_seconds(duration_iso)

        pbar.update(1)

    pbar.close()
    return durations


# =============================================================================
# Ana akış
# =============================================================================
def main() -> None:
    api_key = load_api_key()

    # Girdileri yükle
    raw_videos: list[dict] = load_json(RAW_VIDEOS_PATH, default=[])
    locations: list[dict] = load_json(LOCATIONS_PATH, default=[])

    if not isinstance(raw_videos, list) or not raw_videos:
        sys.exit("[HATA] raw_videos.json boş veya beklenen formatta değil.")
    if not isinstance(locations, list):
        sys.exit("[HATA] locations.json beklenen formatta değil.")

    print(f"[BILGI] Toplam video (raw)     : {len(raw_videos)}")
    print(f"[BILGI] Lokasyon kaydı         : {len(locations)}")

    # Lokasyonları videoId -> (city, country) sözlüğüne dönüştür
    loc_map: dict[str, dict] = {}
    for item in locations:
        vid = item.get("videoId")
        if not vid:
            continue
        loc_map[vid] = {
            "city": item.get("city", "Unknown") or "Unknown",
            "country": item.get("country", "Unknown") or "Unknown",
        }

    # videoId listesi
    video_ids = [v.get("videoId") for v in raw_videos if v.get("videoId")]
    if not video_ids:
        sys.exit("[HATA] raw_videos.json içinde videoId bulunamadı.")

    # YouTube client
    youtube = build("youtube", "v3", developerKey=api_key)

    # Süreleri batch'ler halinde çek
    durations = fetch_durations(youtube, video_ids)
    print(f"[BILGI] Süre çekilen video    : {len(durations)}")

    # Filtrele ve birleştir
    final_data: list[dict] = []
    shorts_filtered = 0
    unknown_filtered = 0
    no_duration = 0

    for video in raw_videos:
        vid = video.get("videoId")
        if not vid:
            continue

        duration_sec = durations.get(vid)
        if duration_sec is None:
            no_duration += 1
            continue

        # Shorts elemesi: 60 saniye ve altı ELENİR
        if duration_sec <= SHORTS_THRESHOLD_SEC:
            shorts_filtered += 1
            continue

        loc = loc_map.get(vid)
        country = (loc or {}).get("country", "Unknown")
        city = (loc or {}).get("city", "Unknown")

        # country 'Unknown' ise elenir
        if not country or country.strip().lower() == "unknown":
            unknown_filtered += 1
            continue

        final_data.append(
            {
                "videoId": vid,
                "title": video.get("title", ""),
                "publishedAt": video.get("publishedAt", ""),
                "thumbnailUrl": video.get("thumbnailUrl", ""),
                "city": city,
                "country": country,
                "duration_seconds": duration_sec,
            }
        )

    # Kaydet
    save_json(OUTPUT_PATH, final_data)

    # Özet
    print("\n[ÖZET]")
    print(f"  Toplam ham video           : {len(raw_videos)}")
    print(f"  Süresi çekilemeyen         : {no_duration}")
    print(f"  Shorts olduğu için elenen  : {shorts_filtered}")
    print(f"  Country 'Unknown' elenen   : {unknown_filtered}")
    print(f"  Final kayıt sayısı         : {len(final_data)}")
    print(f"[OK] Kaydedildi -> {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
