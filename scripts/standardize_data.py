# =============================================================================
# standardize_data.py
# -----------------------------------------------------------------------------
# KURULUM (ÖNEMLİ):
#     pip install google-genai python-dotenv
# =============================================================================
"""
'data/final_map_with_coords.json' dosyasındaki 'country' alanını
ISO 3166-1 alpha-3 koduna standardize eder.

İş akışı:
  1) JSON'u oku, benzersiz 'country' değerlerini topla.
  2) Her biri için (iso3, country_name_en) çözümle:
       - Önce yerleşik COUNTRY_MAP'e bak (hızlı + otoriter).
       - Haritada yoksa Gemini'ye batch tek prompt'la sor (opsiyonel).
       - Gemini de kullanılamıyorsa uyarı ver, kaydı olduğu gibi bırak.
  3) Tüm kayıtları güncelle:
       - country  -> 3 harfli ISO kodu (örn: 'USA', 'TUR', 'MNG')
       - country_name -> tam İngilizce ad (örn: 'United States', 'Turkey')
  4) Mevcut dosyayı zaman damgalı olarak yedekle, sonra üzerine yaz.
  5) (Varsa) 'frontend/src/data/final_map_with_coords.json' kopyasını da güncelle.

Notlar:
  - Idempotent: Daha önce standardize edilmiş (country zaten 3-letter ISO)
    kayıtlar dokunulmadan bırakılır.
  - Resume-friendly: Script birden çok kez güvenle çalıştırılabilir.
  - Ağ/Gemini olmadan da tamamen çalışır: mevcut 64 ülke değeri zaten
    yerleşik haritada.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sys
import time
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any

# =============================================================================
# Yol sabitleri
# =============================================================================
SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent
DATA_DIR = ROOT_DIR / "data"
INPUT_PATH = DATA_DIR / "final_map_with_coords.json"
FRONTEND_MIRROR = ROOT_DIR / "frontend" / "src" / "data" / "final_map_with_coords.json"
ENV_PATH = ROOT_DIR / ".env"

# =============================================================================
# Yerleşik ülke haritası
# -----------------------------------------------------------------------------
# Anahtar: norm(country) — lowercase + ASCII katlanmış (ör. 'İsviçre' -> 'isvicre')
# Değer: (iso3, english_name)
#
# Hem İngilizce hem Türkçe isimleri, sık rastlanan varyantlarla birlikte
# kapsar. Yeni girdi için Gemini fallback devreye girer; bu harita hızlı yol.
# =============================================================================
COUNTRY_MAP: dict[str, tuple[str, str]] = {
    # --- Amerika ---
    "usa":                                ("USA", "United States"),
    "u s a":                              ("USA", "United States"),
    "us":                                 ("USA", "United States"),
    "united states":                      ("USA", "United States"),
    "united states of america":           ("USA", "United States"),
    "america":                            ("USA", "United States"),
    "abd":                                ("USA", "United States"),
    "amerika":                            ("USA", "United States"),
    "amerika birlesik devletleri":        ("USA", "United States"),
    "us virgin islands":                  ("VIR", "U.S. Virgin Islands"),
    "u s virgin islands":                 ("VIR", "U.S. Virgin Islands"),
    "abd virgin adalari":                 ("VIR", "U.S. Virgin Islands"),
    "puerto rico":                        ("PRI", "Puerto Rico"),

    # --- Latin Amerika ---
    "argentina":                          ("ARG", "Argentina"),
    "arjantin":                           ("ARG", "Argentina"),
    "brazil":                             ("BRA", "Brazil"),
    "brasil":                             ("BRA", "Brazil"),
    "brezilya":                           ("BRA", "Brazil"),
    "colombia":                           ("COL", "Colombia"),
    "kolombiya":                          ("COL", "Colombia"),
    "mexico":                             ("MEX", "Mexico"),
    "meksika":                            ("MEX", "Mexico"),
    "peru":                               ("PER", "Peru"),
    "panama":                             ("PAN", "Panama"),
    "uruguay":                            ("URY", "Uruguay"),
    "venezuela":                          ("VEN", "Venezuela"),
    "dominican republic":                 ("DOM", "Dominican Republic"),
    "dominik cumhuriyeti":                ("DOM", "Dominican Republic"),

    # --- Avrupa ---
    "albania":                            ("ALB", "Albania"),
    "arnavutluk":                         ("ALB", "Albania"),
    "andorra":                            ("AND", "Andorra"),
    "austria":                            ("AUT", "Austria"),
    "avusturya":                          ("AUT", "Austria"),
    "france":                             ("FRA", "France"),
    "fransa":                             ("FRA", "France"),
    "germany":                            ("DEU", "Germany"),
    "almanya":                            ("DEU", "Germany"),
    "deutschland":                        ("DEU", "Germany"),
    "greece":                             ("GRC", "Greece"),
    "yunanistan":                         ("GRC", "Greece"),
    "hungary":                            ("HUN", "Hungary"),
    "macaristan":                         ("HUN", "Hungary"),
    "italy":                              ("ITA", "Italy"),
    "italia":                             ("ITA", "Italy"),
    "italya":                             ("ITA", "Italy"),
    "kosovo":                             ("XKX", "Kosovo"),
    "liechtenstein":                      ("LIE", "Liechtenstein"),
    "monaco":                             ("MCO", "Monaco"),
    "montenegro":                         ("MNE", "Montenegro"),
    "karadag":                            ("MNE", "Montenegro"),
    "north macedonia":                    ("MKD", "North Macedonia"),
    "macedonia":                          ("MKD", "North Macedonia"),
    "norway":                             ("NOR", "Norway"),
    "norvec":                             ("NOR", "Norway"),
    "romania":                            ("ROU", "Romania"),
    "romanya":                            ("ROU", "Romania"),
    "russia":                             ("RUS", "Russia"),
    "russian federation":                 ("RUS", "Russia"),
    "rusya":                              ("RUS", "Russia"),
    "serbia":                             ("SRB", "Serbia"),
    "sirbistan":                          ("SRB", "Serbia"),
    "switzerland":                        ("CHE", "Switzerland"),
    "isvicre":                            ("CHE", "Switzerland"),
    "turkey":                             ("TUR", "Turkey"),
    "turkiye":                            ("TUR", "Turkey"),
    "united kingdom":                     ("GBR", "United Kingdom"),
    "uk":                                 ("GBR", "United Kingdom"),
    "great britain":                      ("GBR", "United Kingdom"),
    "ingiltere":                          ("GBR", "United Kingdom"),
    "spain":                              ("ESP", "Spain"),
    "ispanya":                            ("ESP", "Spain"),
    "netherlands":                        ("NLD", "Netherlands"),
    "hollanda":                           ("NLD", "Netherlands"),
    "belgium":                            ("BEL", "Belgium"),
    "belcika":                            ("BEL", "Belgium"),
    "portugal":                           ("PRT", "Portugal"),
    "portekiz":                           ("PRT", "Portugal"),
    "poland":                             ("POL", "Poland"),
    "polonya":                            ("POL", "Poland"),
    "czech republic":                     ("CZE", "Czech Republic"),
    "czechia":                            ("CZE", "Czech Republic"),
    "cekya":                              ("CZE", "Czech Republic"),

    # --- Orta Doğu / Kuzey Afrika ---
    "egypt":                              ("EGY", "Egypt"),
    "misir":                              ("EGY", "Egypt"),
    "jordan":                             ("JOR", "Jordan"),
    "urdun":                              ("JOR", "Jordan"),
    "kuwait":                             ("KWT", "Kuwait"),
    "kuveyt":                             ("KWT", "Kuwait"),
    "lebanon":                            ("LBN", "Lebanon"),
    "lubnan":                             ("LBN", "Lebanon"),
    "oman":                               ("OMN", "Oman"),
    "umman":                              ("OMN", "Oman"),
    "saudi arabia":                       ("SAU", "Saudi Arabia"),
    "suudi arabistan":                    ("SAU", "Saudi Arabia"),
    "syria":                              ("SYR", "Syria"),
    "suriye":                             ("SYR", "Syria"),
    "united arab emirates":               ("ARE", "United Arab Emirates"),
    "uae":                                ("ARE", "United Arab Emirates"),
    "birlesik arap emirlikleri":          ("ARE", "United Arab Emirates"),
    "iran":                               ("IRN", "Iran"),
    "iran islamic republic of":           ("IRN", "Iran"),
    "iraq":                               ("IRQ", "Iraq"),
    "irak":                               ("IRQ", "Iraq"),
    "israel":                             ("ISR", "Israel"),
    "israil":                             ("ISR", "Israel"),

    # --- Orta Asya / Kafkasya ---
    "kazakhstan":                         ("KAZ", "Kazakhstan"),
    "kazakistan":                         ("KAZ", "Kazakhstan"),
    "uzbekistan":                         ("UZB", "Uzbekistan"),
    "ozbekistan":                         ("UZB", "Uzbekistan"),
    "kyrgyzstan":                         ("KGZ", "Kyrgyzstan"),
    "kirgizistan":                        ("KGZ", "Kyrgyzstan"),
    "tajikistan":                         ("TJK", "Tajikistan"),
    "tacikistan":                         ("TJK", "Tajikistan"),
    "turkmenistan":                       ("TKM", "Turkmenistan"),
    "azerbaijan":                         ("AZE", "Azerbaijan"),
    "azerbaycan":                         ("AZE", "Azerbaijan"),
    "georgia":                            ("GEO", "Georgia"),
    "gurcistan":                          ("GEO", "Georgia"),
    "armenia":                            ("ARM", "Armenia"),
    "ermenistan":                         ("ARM", "Armenia"),

    # --- Güney Asya ---
    "bangladesh":                         ("BGD", "Bangladesh"),
    "banglades":                          ("BGD", "Bangladesh"),
    "india":                              ("IND", "India"),
    "hindistan":                          ("IND", "India"),
    "nepal":                              ("NPL", "Nepal"),
    "pakistan":                           ("PAK", "Pakistan"),
    "sri lanka":                          ("LKA", "Sri Lanka"),

    # --- Doğu / Güneydoğu Asya ---
    "china":                              ("CHN", "China"),
    "cin":                                ("CHN", "China"),
    "japan":                              ("JPN", "Japan"),
    "japonya":                            ("JPN", "Japan"),
    "south korea":                        ("KOR", "South Korea"),
    "korea":                              ("KOR", "South Korea"),
    "guney kore":                         ("KOR", "South Korea"),
    "north korea":                        ("PRK", "North Korea"),
    "kuzey kore":                         ("PRK", "North Korea"),
    "taiwan":                             ("TWN", "Taiwan"),
    "tayvan":                             ("TWN", "Taiwan"),
    "mongolia":                           ("MNG", "Mongolia"),
    "mogolistan":                         ("MNG", "Mongolia"),
    "cambodia":                           ("KHM", "Cambodia"),
    "kambocya":                           ("KHM", "Cambodia"),
    "indonesia":                          ("IDN", "Indonesia"),
    "endonezya":                          ("IDN", "Indonesia"),
    "laos":                               ("LAO", "Laos"),
    "malaysia":                           ("MYS", "Malaysia"),
    "malezya":                            ("MYS", "Malaysia"),
    "thailand":                           ("THA", "Thailand"),
    "tayland":                            ("THA", "Thailand"),
    "vietnam":                            ("VNM", "Vietnam"),
    "viet nam":                           ("VNM", "Vietnam"),
}


# =============================================================================
# Yardımcılar
# =============================================================================
def norm(s: str) -> str:
    """Lowercase + ASCII katlama (diacritics silinir) + whitespace normalize."""
    if not s:
        return ""
    # NFKD ile ayrışmayan özel harfleri (ör. Türkçe ı / dotless-i) elle eşle.
    # Bunlar NFKD decomposition'ına sahip değiller; ASCII katlama onları
    # tamamen silerdi.
    translit = {
        "ı": "i", "I": "I",         # dotless/dotted i (küçük harf ı NFKD yok)
        "ş": "s", "Ş": "S",
        "ğ": "g", "Ğ": "G",
        "ç": "c", "Ç": "C",
        "ö": "o", "Ö": "O",
        "ü": "u", "Ü": "U",
        "ñ": "n", "Ñ": "N",
        "ß": "ss",
        "ø": "o", "Ø": "O",
        "æ": "ae", "Æ": "AE",
        "œ": "oe", "Œ": "OE",
    }
    s = "".join(translit.get(ch, ch) for ch in s)
    # NFKD ile aksanlı karakterleri ayrıştır, non-ASCII'yi at.
    folded = unicodedata.normalize("NFKD", s)
    folded = folded.encode("ascii", "ignore").decode("ascii")
    # Noktalama -> boşluk; çoklu boşlukları tekille.
    folded = re.sub(r"[.,()'`\-]", " ", folded)
    folded = re.sub(r"\s+", " ", folded).strip().lower()
    return folded


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: Any) -> None:
    """Atomik yazım (tmp -> rename)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp.replace(path)


def is_iso3(s: str) -> bool:
    """3 harfli büyük harfli ISO kodu mu?"""
    return isinstance(s, str) and bool(re.fullmatch(r"[A-Z]{3}", s))


# =============================================================================
# Gemini fallback (opsiyonel — ağ yoksa sessizce atlanır)
# =============================================================================
def resolve_with_gemini(unknown_names: list[str]) -> dict[str, tuple[str, str]]:
    """
    Yerleşik haritada bulunamayan ülke isimlerini Gemini'ye TEK prompt ile
    sorar. Başarısız olursa boş dict döner.

    Returns: {original_name: (iso3, english_name)}
    """
    if not unknown_names:
        return {}

    try:
        from dotenv import load_dotenv
        from google import genai
    except ImportError:
        print(
            "[UYARI] google-genai / python-dotenv yok; Gemini fallback atlandı.\n"
            "        pip install google-genai python-dotenv"
        )
        return {}

    if ENV_PATH.exists():
        load_dotenv(dotenv_path=ENV_PATH)
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("[UYARI] .env içinde GEMINI_API_KEY yok; Gemini fallback atlandı.")
        return {}

    client = genai.Client(api_key=api_key)

    prompt = (
        "Sana ülke isimleri listesi veriyorum (farklı dillerde veya "
        "yazım varyantlarında olabilir). Her biri için ISO 3166-1 alpha-3 "
        "standart ülke kodunu ve tam İngilizce ülke adını döndür.\n"
        "SADECE şu formatta bir JSON array dön, başka hiçbir açıklama ekleme:\n"
        '[{"input": "<orijinal>", "iso3": "<3 harfli büyük kod>", "name": "<İngilizce ad>"}]\n'
        "Ülkeyi tanımlayamıyorsan iso3 değerini null olarak bırak.\n\n"
        "İSİMLER:\n" + "\n".join(f"- {n}" for n in unknown_names)
    )

    for model_name in ("gemini-2.0-flash", "gemini-flash-latest"):
        try:
            resp = client.models.generate_content(
                model=model_name, contents=prompt
            )
            text = (resp.text or "").strip()
            # ```json ... ``` temizliği
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
            # İlk [ ... son ]
            l = text.find("[")
            r = text.rfind("]")
            if l != -1 and r != -1:
                text = text[l : r + 1]
            items = json.loads(text)
            out: dict[str, tuple[str, str]] = {}
            for it in items:
                if not isinstance(it, dict):
                    continue
                inp = str(it.get("input", "")).strip()
                iso = (it.get("iso3") or "")
                name = str(it.get("name", "")).strip()
                if inp and isinstance(iso, str) and is_iso3(iso.upper()):
                    out[inp] = (iso.upper(), name or inp)
            print(f"[BILGI] Gemini ({model_name}) ile çözüldü: {len(out)} giriş")
            return out
        except Exception as e:
            print(f"[UYARI] Gemini çağrısı başarısız ({model_name}): {e}")
            time.sleep(1.0)

    return {}


# =============================================================================
# Ana akış
# =============================================================================
def main() -> int:
    if not INPUT_PATH.exists():
        print(f"[HATA] Dosya bulunamadı: {INPUT_PATH}", file=sys.stderr)
        return 1

    records = load_json(INPUT_PATH)
    if not isinstance(records, list):
        print("[HATA] Beklenen: liste; okunan yapı farklı.", file=sys.stderr)
        return 1

    print(f"[BILGI] Kaynak kayıt sayısı : {len(records)}")

    # 1) Benzersiz country değerleri
    uniques: list[str] = sorted({(r.get("country") or "").strip()
                                 for r in records
                                 if r.get("country")})
    print(f"[BILGI] Benzersiz country   : {len(uniques)}")

    # 2) Yerleşik haritadan çözümle
    resolved: dict[str, tuple[str, str]] = {}
    unresolved: list[str] = []

    # Bilinen ISO3 kodları — is_iso3 tek başına yetmiyor çünkü 'ABD'
    # gibi Türkçe kısaltmalar da [A-Z]{3} regex'ine uyuyor.
    known_iso3 = {iso for iso, _ in COUNTRY_MAP.values()}

    for raw in uniques:
        # Önce yerleşik haritaya bak — ABD gibi Türkçe kısaltmaları yakalar.
        mapped = COUNTRY_MAP.get(norm(raw))
        if mapped:
            resolved[raw] = mapped
            continue
        # Map'te yoksa ve gerçekten bilinen bir ISO3 ise dokunma.
        if is_iso3(raw) and raw in known_iso3:
            resolved[raw] = (raw, "")  # name'i sonradan doldururuz
            continue
        unresolved.append(raw)

    print(f"[BILGI] Harita ile çözüldü  : {len(resolved)}")
    print(f"[BILGI] Gemini'ye gidecek   : {len(unresolved)}")
    if unresolved:
        for u in unresolved:
            print(f"         - {u!r}")

    # 3) Gemini fallback (opsiyonel)
    if unresolved:
        gemini_out = resolve_with_gemini(unresolved)
        for raw in unresolved:
            if raw in gemini_out:
                resolved[raw] = gemini_out[raw]
            else:
                print(f"[UYARI] Çözülemedi, orijinal korunacak: {raw!r}")

    # 4) ISO3-only kayıtların name'ini haritadan tamamla (varsa)
    for raw, (iso, name) in list(resolved.items()):
        if is_iso3(raw) and not name:
            # Mevcut haritadan ters arama
            english = ""
            for _, (rx_iso, rx_name) in COUNTRY_MAP.items():
                if rx_iso == iso:
                    english = rx_name
                    break
            resolved[raw] = (iso, english or raw)

    # 5) Yedek al
    if INPUT_PATH.exists():
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = INPUT_PATH.with_name(
            f"final_map_with_coords.backup-{ts}.json"
        )
        shutil.copy2(INPUT_PATH, backup)
        print(f"[OK]   Yedek oluşturuldu    : {backup.name}")

    # 6) Kayıtları güncelle
    updated = 0
    untouched = 0
    for r in records:
        raw = (r.get("country") or "").strip()
        if not raw:
            continue
        entry = resolved.get(raw)
        if not entry:
            untouched += 1
            continue
        iso, name = entry
        if r.get("country") != iso or r.get("country_name") != name:
            r["country"] = iso
            if name:
                r["country_name"] = name
            updated += 1

    print(f"[BILGI] Güncellenen kayıt   : {updated}")
    print(f"[BILGI] Değişmeyen          : {len(records) - updated}")
    if untouched:
        print(f"[UYARI] Çözülemediği için dokunulmayan: {untouched}")

    # 7) Yaz (hem data/ hem frontend mirror)
    save_json(INPUT_PATH, records)
    print(f"[OK]   Yazıldı              : {INPUT_PATH}")

    if FRONTEND_MIRROR.exists() or FRONTEND_MIRROR.parent.exists():
        save_json(FRONTEND_MIRROR, records)
        print(f"[OK]   Frontend mirror      : {FRONTEND_MIRROR}")

    # 8) Özet mapping çıktısı
    print("\n[MAPPING]")
    for raw in uniques:
        entry = resolved.get(raw)
        if entry:
            iso, name = entry
            print(f"  {raw!r:<40} -> {iso}  ({name})")
        else:
            print(f"  {raw!r:<40} -> (çözümlenemedi)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
