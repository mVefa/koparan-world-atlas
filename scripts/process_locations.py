# =============================================================================
# process_locations.py
# -----------------------------------------------------------------------------
# KURULUM (ÖNEMLİ):
#     pip install google-genai python-dotenv tqdm
#
# NOT: Bu script ESKİ 'google-generativeai' paketini DEĞİL,
#      YENİ 'google-genai' SDK'sını kullanır.
# =============================================================================
"""
'data/raw_videos.json' içindeki videoların başlık + açıklamalarını temizleyip
Gemini modeline 50'lik gruplar halinde TEK bir istekle göndererek her video
için (videoId, city, country) bilgisini çıkartır ve 'data/locations.json'
dosyasına kaydeder.

Özellikler:
  - Batch Processing : 50'lik gruplar; her batch tek bir Gemini prompt'u.
  - Model Fallback   : Birincil 'gemini-2.0-flash', yedek 'gemini-flash-latest'.
  - Resumable        : 'data/locations.json' kontrol edilir; yalnızca eksik
                       videolar için istek atılır. Her batch sonrası diske yazılır.
  - Temizleme        : re modülüyle URL, reklam, sosyal medya, hashtag temizliği.
  - Hata Yön.        : Kota/rate-limit veya beklenmeyen hatada mevcut veri
                       kaydedilir, script güvenli şekilde sonlanır.
  - tqdm             : 'Batch X/Y işleniyor...' biçiminde ilerleme çubuğu.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from tqdm import tqdm

# -----------------------------------------------------------------------------
# Yeni SDK (google-genai)
# -----------------------------------------------------------------------------
try:
    from google import genai
except ImportError:
    sys.exit(
        "[HATA] 'google-genai' kütüphanesi yüklü değil.\n"
        "       Kurulum: pip install google-genai"
    )

# =============================================================================
# Sabitler
# =============================================================================
SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent
ENV_PATH = ROOT_DIR / ".env"
DATA_DIR = ROOT_DIR / "data"
RAW_VIDEOS_PATH = DATA_DIR / "raw_videos.json"
LOCATIONS_PATH = DATA_DIR / "locations.json"

MODEL_NAME = "gemini-2.0-flash"
FALLBACK_MODEL_NAME = "gemini-flash-latest"

BATCH_SIZE = 50
REQUEST_DELAY_SEC = 0.5          # batch'ler arası hafif gecikme
MAX_DESC_CHARS_PER_VIDEO = 1200  # tek bir prompt şişmesin diye güvenlik sınırı

BATCH_PROMPT_HEADER = (
    "Sana {n} adet videonun başlık ve açıklamasını veriyorum. "
    "Her birinin videoId bilgisini KORUYARAK hangi şehir ve ülkede geçtiğini bul. "
    "SADECE şu formatta bir JSON array dön: "
    '[{{"videoId": "...", "city": "...", "country": "..."}}]\n'
    "ÇOK ÖNEMLİ KURAL — country alanı: Ülke ismini TAM AD olarak değil, "
    "SADECE ISO 3166-1 alpha-3 standardındaki 3 HARFLİ BÜYÜK HARF ülke kodu "
    "olarak döndür (örnekler: USA, TUR, DEU, FRA, MNG, KAZ, JPN, GBR, BRA, "
    "IDN, THA, VNM, ARE, SAU, KOR, CHN, IND, EGY, RUS, ITA, ESP, NLD, MEX). "
    "Kosovo için XKX kullan. Ülkeyi belirleyemiyorsan country alanına "
    "\"Unknown\" yaz (ISO kodu değil). Tam ülke adı, Türkçe ad veya 2 harfli "
    "kod YAZMA — yalnızca 3 harfli büyük harf ISO alpha-3 kodu.\n"
    "city alanını ise o ülkedeki şehrin tam adı olarak (Türkçe veya İngilizce) "
    "yaz; şehri belirleyemiyorsan \"Unknown\" yaz.\n"
    "Başka hiçbir açıklama ekleme, sadece JSON array.\n\n"
    "VİDEOLAR:\n"
)

# =============================================================================
# Metin temizleme (re kütüphanesi)
# =============================================================================
URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)
HASHTAG_RE = re.compile(r"#\w+", re.UNICODE)

SOCIAL_AD_PATTERNS = [
    r"just\s*english",
    r"instagram[:\s]*@?\S+",
    r"twitter[:\s]*@?\S+",
    r"facebook[:\s]*@?\S+",
    r"tiktok[:\s]*@?\S+",
    r"youtube[:\s]*@?\S+",
    r"telegram[:\s]*@?\S+",
    r"discord[:\s]*@?\S+",
    r"@\w+",
]
SOCIAL_AD_RE = re.compile("|".join(SOCIAL_AD_PATTERNS), re.IGNORECASE)

POPULAR_CUTOFF_RE = re.compile(r"en\s+pop[uü]ler\s+videolar[ıi]m", re.IGNORECASE)


def clean_text(text: str) -> str:
    """Açıklamayı Gemini'ye göndermeden önce temizler."""
    if not text:
        return ""

    m = POPULAR_CUTOFF_RE.search(text)
    if m:
        text = text[: m.start()]

    text = URL_RE.sub("", text)
    text = SOCIAL_AD_RE.sub("", text)
    text = HASHTAG_RE.sub("", text)

    lines = [line.strip() for line in text.splitlines()]
    lines = [line for line in lines if line]
    cleaned = "\n".join(lines)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)

    return cleaned.strip()


# =============================================================================
# Yardımcılar
# =============================================================================
def load_api_key() -> str:
    if not ENV_PATH.exists():
        sys.exit(f"[HATA] .env dosyası bulunamadı: {ENV_PATH}")

    load_dotenv(dotenv_path=ENV_PATH)
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        sys.exit(
            "[HATA] .env dosyasında GEMINI_API_KEY (veya GOOGLE_API_KEY) tanımlı değil."
        )
    return api_key


def load_json(path: Path, default: Any):
    if not path.exists():
        return default
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        print(f"[UYARI] {path} bozuk, varsayılan değer kullanılacak.")
        return default


def save_json(path: Path, data: Any) -> None:
    """Atomik yazım: .tmp -> rename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp_path.replace(path)


# =============================================================================
# Batch prompt inşası ve response parse işlemleri
# =============================================================================
def build_batch_prompt(batch: list[dict]) -> str:
    """Batch için tek bir prompt üretir."""
    lines: list[str] = [BATCH_PROMPT_HEADER.format(n=len(batch))]

    for idx, video in enumerate(batch, start=1):
        video_id = video.get("videoId", "")
        title = (video.get("title") or "").strip()
        description_raw = video.get("description") or ""
        description = clean_text(description_raw)

        # Aşırı uzun açıklamaları kısalt
        if len(description) > MAX_DESC_CHARS_PER_VIDEO:
            description = description[:MAX_DESC_CHARS_PER_VIDEO] + " ..."

        lines.append(
            f"---\n"
            f"#{idx}\n"
            f"videoId: {video_id}\n"
            f"title: {title}\n"
            f"description: {description}"
        )

    lines.append("---\n")
    return "\n".join(lines)


def extract_json_array(raw_text: str) -> list[dict]:
    """
    Gemini cevabındaki JSON array'i çıkartır. Model bazen ```json ... ```
    bloğu içinde dönebilir; sağlam bir ayrıştırma uygularız.
    """
    if not raw_text:
        return []

    text = raw_text.strip()

    # kod bloklarını temizle
    text = re.sub(r"^```(?:json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()

    # İlk [ ile son ] arası içeriği al (array'i yakalamaya çalış)
    start = text.find("[")
    end = text.rfind("]")
    if start != -1 and end != -1 and end > start:
        text = text[start : end + 1]

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []

    if not isinstance(data, list):
        return []

    normalized: list[dict] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        normalized.append(
            {
                "videoId": str(item.get("videoId", "")).strip(),
                "city": (str(item.get("city", "Unknown")).strip() or "Unknown"),
                "country": (str(item.get("country", "Unknown")).strip() or "Unknown"),
            }
        )
    return normalized


# =============================================================================
# Gemini isteği (birincil + yedek model fallback)
# =============================================================================
_ACTIVE_MODEL = MODEL_NAME


def _generate(client, model_name: str, prompt: str):
    return client.models.generate_content(model=model_name, contents=prompt)


def _extract_text(response) -> str:
    raw_text = ""
    try:
        raw_text = response.text or ""
    except Exception:
        raw_text = ""

    if not raw_text:
        candidates = getattr(response, "candidates", None) or []
        if candidates:
            content = getattr(candidates[0], "content", None)
            parts = getattr(content, "parts", None) or []
            raw_text = "".join(getattr(p, "text", "") or "" for p in parts)
    return raw_text


def ask_gemini_batch(client, batch: list[dict]) -> list[dict]:
    """Tek bir istekle tüm batch'i işler. Model hatası olursa yedeğe geçer."""
    global _ACTIVE_MODEL
    prompt = build_batch_prompt(batch)

    try:
        response = _generate(client, _ACTIVE_MODEL, prompt)
    except Exception as primary_err:
        if _ACTIVE_MODEL == FALLBACK_MODEL_NAME:
            raise
        print(
            f"\n[UYARI] Birincil model '{_ACTIVE_MODEL}' hata verdi: {primary_err}\n"
            f"[BILGI] Yedek modele geçiliyor: '{FALLBACK_MODEL_NAME}'"
        )
        _ACTIVE_MODEL = FALLBACK_MODEL_NAME
        response = _generate(client, _ACTIVE_MODEL, prompt)

    raw_text = _extract_text(response)
    return extract_json_array(raw_text)


# =============================================================================
# Ana akış
# =============================================================================
def is_quota_or_rate_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    keywords = ("quota", "rate limit", "resource_exhausted", "429")
    return any(k in msg for k in keywords)


def main() -> None:
    api_key = load_api_key()
    client = genai.Client(api_key=api_key)

    print(f"[BILGI] Birincil model : {MODEL_NAME}")
    print(f"[BILGI] Yedek model    : {FALLBACK_MODEL_NAME}")
    print(f"[BILGI] Batch size     : {BATCH_SIZE}")

    if not RAW_VIDEOS_PATH.exists():
        sys.exit(f"[HATA] Girdi dosyası bulunamadı: {RAW_VIDEOS_PATH}")

    raw_videos: list[dict] = load_json(RAW_VIDEOS_PATH, default=[])
    if not isinstance(raw_videos, list) or not raw_videos:
        sys.exit("[HATA] raw_videos.json boş veya beklenen formatta değil.")

    # --- Resumable: mevcut kayıtlar ---
    existing: list[dict] = load_json(LOCATIONS_PATH, default=[])
    processed_ids = {item["videoId"] for item in existing if "videoId" in item}

    pending = [v for v in raw_videos if v.get("videoId") not in processed_ids]

    print(f"[BILGI] Toplam video    : {len(raw_videos)}")
    print(f"[BILGI] Zaten işlenmiş  : {len(processed_ids)}")
    print(f"[BILGI] İşlenecek video : {len(pending)}")

    if not pending:
        print("[OK] İşlenecek yeni video yok.")
        return

    results: list[dict] = list(existing)
    stop_reason: str | None = None

    # Batch sayısı
    total_batches = (len(pending) + BATCH_SIZE - 1) // BATCH_SIZE

    pbar = tqdm(total=total_batches, unit="batch", ncols=100)

    try:
        for batch_index in range(total_batches):
            start = batch_index * BATCH_SIZE
            batch = pending[start : start + BATCH_SIZE]

            # Hızlı videoId -> title eşlemesi (kayıtlara title da yazmak için)
            id_to_title = {v.get("videoId"): (v.get("title") or "").strip() for v in batch}
            batch_ids = set(id_to_title.keys())

            pbar.set_description(f"Batch {batch_index + 1}/{total_batches} işleniyor")

            try:
                batch_results = ask_gemini_batch(client, batch)
            except Exception as e:
                if is_quota_or_rate_error(e):
                    stop_reason = f"Kota/rate-limit hatası: {e}"
                else:
                    stop_reason = f"API hatası: {e}"
                raise

            # Gemini'den gelenleri videoId ile eşleştir
            received_ids: set[str] = set()
            for item in batch_results:
                vid = item.get("videoId", "")
                if vid not in batch_ids:
                    # Model hatalı/uydurma videoId döndürdüyse atla
                    continue
                received_ids.add(vid)
                results.append(
                    {
                        "videoId": vid,
                        "title": id_to_title.get(vid, ""),
                        "city": item.get("city", "Unknown"),
                        "country": item.get("country", "Unknown"),
                    }
                )

            # Batch'te yanıtı alınmamış videolar için 'Unknown' kaydı
            missing_ids = batch_ids - received_ids
            if missing_ids:
                print(
                    f"\n[UYARI] Batch {batch_index + 1}: {len(missing_ids)} video "
                    f"için yanıt eksik, 'Unknown' olarak kaydediliyor."
                )
                for vid in missing_ids:
                    results.append(
                        {
                            "videoId": vid,
                            "title": id_to_title.get(vid, ""),
                            "city": "Unknown",
                            "country": "Unknown",
                        }
                    )

            # Her batch sonrası diske yaz -> resumable
            save_json(LOCATIONS_PATH, results)
            pbar.update(1)

            if batch_index < total_batches - 1:
                time.sleep(REQUEST_DELAY_SEC)

    except KeyboardInterrupt:
        stop_reason = "Kullanıcı iptal etti (Ctrl+C)."
    except Exception as e:
        if stop_reason is None:
            stop_reason = f"Beklenmeyen hata: {e}"
    finally:
        pbar.close()
        save_json(LOCATIONS_PATH, results)
        print(f"[OK] Kaydedildi -> {LOCATIONS_PATH} (toplam {len(results)} kayıt)")
        print(f"[BILGI] Son aktif model: {_ACTIVE_MODEL}")
        if stop_reason:
            print(f"[DURDU] {stop_reason}")
            print("[BILGI] Scripti tekrar çalıştırdığında kaldığı yerden devam eder.")
            sys.exit(1)


if __name__ == "__main__":
    main()
