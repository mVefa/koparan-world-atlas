# =============================================================================
# geocoder.py
# -----------------------------------------------------------------------------
# KURULUM (ÖNEMLİ):
#     pip install geopy tqdm
# =============================================================================
"""
'data/final_refined_data.json' içindeki her kaydın (city, country) bilgisini
OpenStreetMap Nominatim üzerinden lat/lng'e çevirir ve
'data/final_map_with_coords.json' dosyasına kaydeder.

Kurallar:
  - city 'Unknown' değilse arama sorgusu: "city, country".
    city 'Unknown' ise sorgu: "country".
  - Her istek arasında 1 saniye bekleme (Nominatim nezaketi, engellenmemek için).
  - Koordinat bulunamazsa lat/lng değerleri None bırakılır.
  - Caching: 'data/final_map_with_coords.json' zaten varsa, koordinatı OLAN
    kayıtlar tekrar sorgulanmaz; sadece eksik olanlar işlenir.
  - Aynı (city, country) kombinasyonu için de runtime cache tutulur; aynı
    lokasyon ikinci kez API'ye sorulmaz.
  - tqdm ile ilerleme gösterimi.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

from tqdm import tqdm

try:
    from geopy.exc import (
        GeocoderServiceError,
        GeocoderTimedOut,
        GeocoderUnavailable,
    )
    from geopy.geocoders import Nominatim
except ImportError:
    sys.exit(
        "[HATA] 'geopy' kütüphanesi yüklü değil.\n"
        "       Kurulum: pip install geopy"
    )

# =============================================================================
# Yol sabitleri
# =============================================================================
SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent
DATA_DIR = ROOT_DIR / "data"
INPUT_PATH = DATA_DIR / "final_refined_data.json"
OUTPUT_PATH = DATA_DIR / "final_map_with_coords.json"

# =============================================================================
# Sabitler
# =============================================================================
USER_AGENT = "koparan-map-geocoder/1.0 (contact: yoksulmuhammet@gmail.com)"
SLEEP_SEC = 1.0           # Nominatim: saniyede max 1 istek
REQUEST_TIMEOUT = 15      # saniye
MAX_RETRIES = 2           # geçici hatalarda yeniden deneme sayısı
SAVE_EVERY_N = 10         # bu kadar kayıtta bir diske yaz (güvenlik için)


# =============================================================================
# Yardımcılar
# =============================================================================
def load_json(path: Path, default: Any = None):
    if not path.exists():
        if default is not None:
            return default
        sys.exit(f"[HATA] Dosya bulunamadı: {path}")
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        sys.exit(f"[HATA] {path} parse edilemedi: {e}")


def save_json(path: Path, data: Any) -> None:
    """Atomik yazım."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp_path.replace(path)


def build_query(city: str, country: str) -> str:
    """Sorgu stringini kurallara göre oluştur."""
    city = (city or "").strip()
    country = (country or "").strip()

    if city and city.lower() != "unknown":
        return f"{city}, {country}".strip(", ")
    return country


def has_coords(record: dict) -> bool:
    return record.get("lat") is not None and record.get("lng") is not None


# =============================================================================
# Nominatim sorgusu
# =============================================================================
def geocode_query(geolocator: Nominatim, query: str) -> tuple[float | None, float | None]:
    """
    Verilen sorgu için (lat, lng) döner. Başarısız olursa (None, None).
    Geçici hatalarda kısa bir bekleme ile yeniden dener.
    """
    if not query:
        return None, None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            location = geolocator.geocode(query, timeout=REQUEST_TIMEOUT)
            if location is not None:
                return float(location.latitude), float(location.longitude)
            return None, None
        except (GeocoderTimedOut, GeocoderUnavailable, GeocoderServiceError) as e:
            if attempt >= MAX_RETRIES:
                print(f"\n[UYARI] Sorgu başarısız ({query!r}): {e}")
                return None, None
            time.sleep(2 * attempt)  # geri çekil
        except Exception as e:
            print(f"\n[UYARI] Beklenmeyen hata ({query!r}): {e}")
            return None, None

    return None, None


# =============================================================================
# Ana akış
# =============================================================================
def main() -> None:
    # Girdiyi yükle
    refined: list[dict] = load_json(INPUT_PATH)
    if not isinstance(refined, list) or not refined:
        sys.exit("[HATA] final_refined_data.json boş veya beklenen formatta değil.")

    print(f"[BILGI] Kaynak kayıt sayısı : {len(refined)}")

    # Mevcut çıktı var mı? (caching)
    existing: list[dict] = load_json(OUTPUT_PATH, default=[]) or []
    existing_by_id: dict[str, dict] = {
        item["videoId"]: item for item in existing if item.get("videoId")
    }

    # Konum bazlı cache: (city, country) -> (lat, lng)
    location_cache: dict[tuple[str, str], tuple[float | None, float | None]] = {}
    for rec in existing:
        if has_coords(rec):
            key = (
                (rec.get("city") or "").strip().lower(),
                (rec.get("country") or "").strip().lower(),
            )
            location_cache[key] = (rec.get("lat"), rec.get("lng"))

    # Final listeyi mevcut kayıtlardan (varsa) başlat, girdideki sıraya göre yeniden kur
    results: list[dict] = []
    pending_indices: list[int] = []  # results içinde sonradan güncellenecek kayıtların index'i

    for video in refined:
        vid = video.get("videoId")
        base = dict(video)  # videoId, title, publishedAt, thumbnailUrl, city, country, duration_seconds

        cached = existing_by_id.get(vid)
        if cached and has_coords(cached):
            # Mevcut koordinatları koru
            base["lat"] = cached.get("lat")
            base["lng"] = cached.get("lng")
        else:
            # Koordinat eksik -> işlenecek
            base["lat"] = None
            base["lng"] = None
            pending_indices.append(len(results))

        results.append(base)

    already_cached_count = len(results) - len(pending_indices)
    print(f"[BILGI] Önbellekten gelen    : {already_cached_count}")
    print(f"[BILGI] Geocode edilecek     : {len(pending_indices)}")

    if not pending_indices:
        save_json(OUTPUT_PATH, results)
        print(f"[OK] Tüm kayıtlar zaten koordinatlı. Kaydedildi -> {OUTPUT_PATH}")
        return

    # Nominatim client
    geolocator = Nominatim(user_agent=USER_AGENT, timeout=REQUEST_TIMEOUT)

    found = 0
    not_found = 0
    processed_since_save = 0

    pbar = tqdm(total=len(pending_indices), unit="loc", ncols=100, desc="Geocoding")

    try:
        for idx in pending_indices:
            record = results[idx]
            city = record.get("city", "") or ""
            country = record.get("country", "") or ""

            key = (city.strip().lower(), country.strip().lower())

            # Konum cache kontrolü
            if key in location_cache:
                lat, lng = location_cache[key]
            else:
                query = build_query(city, country)
                lat, lng = geocode_query(geolocator, query)
                location_cache[key] = (lat, lng)
                time.sleep(SLEEP_SEC)  # Nominatim'e saygı: her API isteğinden sonra 1sn

            record["lat"] = lat
            record["lng"] = lng

            if lat is not None and lng is not None:
                found += 1
            else:
                not_found += 1

            pbar.update(1)
            processed_since_save += 1

            if processed_since_save >= SAVE_EVERY_N:
                save_json(OUTPUT_PATH, results)
                processed_since_save = 0

    except KeyboardInterrupt:
        print("\n[DURDU] Kullanıcı iptal etti (Ctrl+C). Mevcut veri kaydediliyor...")
    except Exception as e:
        print(f"\n[DURDU] Beklenmeyen hata: {e}. Mevcut veri kaydediliyor...")
    finally:
        pbar.close()
        save_json(OUTPUT_PATH, results)

    print("\n[ÖZET]")
    print(f"  Toplam kayıt           : {len(results)}")
    print(f"  Önbellekten gelen      : {already_cached_count}")
    print(f"  Yeni bulunan koordinat : {found}")
    print(f"  Bulunamayan (None)     : {not_found}")
    print(f"[OK] Kaydedildi -> {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
