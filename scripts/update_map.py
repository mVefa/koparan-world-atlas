import json
import os
from pathlib import Path
from dotenv import load_dotenv
from google import genai
from google.genai import types
import re
from googleapiclient.discovery import build

# 1. DOSYA YOLLARI YAPILANDIRMASI
# Scriptin bulunduğu klasör (scripts/)
SCRIPT_DIR = Path(__file__).resolve().parent
# Proje ana dizini (koparan-world-atlas/)
ROOT_DIR = SCRIPT_DIR.parent
# Hedef JSON dosyası yolu
DATA_FILE = ROOT_DIR / "frontend" / "src" / "data" / "final_map_with_coords.json"
# .env dosyası yolu (ana dizinde varsayıyoruz)
ENV_PATH = ROOT_DIR / ".env"

load_dotenv(ENV_PATH)

def load_current_data():
    """
    Mevcut final_map_with_coords.json dosyasını yükler.
    Dosya yoksa boş bir liste döner.
    """
    if not DATA_FILE.exists():
        print(f"[UYARI] Veri dosyası bulunamadı: {DATA_FILE}")
        return []
    
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[HATA] JSON yüklenirken sorun oluştu: {e}")
        return []

# Test amaçlı hafızayı yükleyelim
current_data = load_current_data()
# Mevcut videoid'leri bir küme (set) içine alalım (Hızlı arama için)
processed_ids = {item["videoId"] for item in current_data}

print(f"[BİLGİ] Hafıza yüklendi. Toplam {len(current_data)} video kayıtlı.")


# SABİTLER
CHANNEL_ID = "UCHut-IQXip7mtXyC3GOiQ1A"
SHORTS_THRESHOLD_SEC = 60

def get_video_duration_seconds(duration_str):
    """
    ISO 8601 süresini (örn: PT15M33S) saniyeye çevirir.
    """
    hours = re.search(r'(\d+)H', duration_str)
    minutes = re.search(r'(\d+)M', duration_str)
    seconds = re.search(r'(\d+)S', duration_str)
    
    h = int(hours.group(1)) if hours else 0
    m = int(minutes.group(1)) if minutes else 0
    s = int(seconds.group(1)) if seconds else 0
    
    return h * 3600 + m * 60 + s

def fetch_new_videos(processed_ids):
    """
    Son 5 videoyu çeker, eskileri ve Shorts'ları eler.
    """
    youtube = build("youtube", "v3", developerKey=os.getenv("YOUTUBE_API_KEY"))
    
    # 1. Son aktiviteleri getir
    request = youtube.activities().list(
        part="snippet,contentDetails",
        channelId=CHANNEL_ID,
        maxResults=5
    )
    response = request.execute()
    
    new_candidates = []
    for item in response.get("items", []):
        if item["snippet"]["type"] == "upload":
            vid = item["contentDetails"]["upload"]["videoId"]
            # Hafıza Kontrolü: Eğer bu ID bizde varsa pas geç
            if vid not in processed_ids:
                new_candidates.append({
                    "videoId": vid,
                    "title": item["snippet"]["title"],
                    "publishedAt": item["snippet"]["publishedAt"],
                    "description": item["snippet"]["description"],
                    "thumbnailUrl": item["snippet"]["thumbnails"].get("maxres", {}).get("url") or \
                                   item["snippet"]["thumbnails"].get("high", {}).get("url")
                })

    if not new_candidates:
        print("[BİLGİ] Yeni video bulunamadı.")
        return []

    # 2. Yeni videoların sürelerini çek ve Shorts filtrele
    video_ids = [v["videoId"] for v in new_candidates]
    details_request = youtube.videos().list(
        part="contentDetails",
        id=",".join(video_ids)
    )
    details_response = details_request.execute()
    
    durations = {item["id"]: get_video_duration_seconds(item["contentDetails"]["duration"]) 
                 for item in details_response.get("items", [])}
    
    final_new_videos = []
    for video in new_candidates:
        duration = durations.get(video["videoId"], 0)
        if duration > SHORTS_THRESHOLD_SEC:
            video["duration_seconds"] = duration
            final_new_videos.append(video)
            print(f"[YENİ] Video tespit edildi: {video['title']} ({duration} sn)")
        else:
            print(f"[SİS] Shorts elendi: {video['title']}")
            
    return final_new_videos

def get_location_info_from_gemini(video_title, video_description):
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    
    prompt = f"""
    Analyze the following YouTube video title and description to identify the location.

    Title: {video_title}
    Description: {video_description}

    STRICT RULES:
    1. 'city': Use the standard English name of the city. 
       - IF YOU ARE NOT SURE about the specific city, write EXACTLY "Unknown".
    2. 'country': Use ONLY the 3-letter ISO 3166-1 alpha-3 code (e.g., 'IDN', 'TUR').
    3. 'country_name': Use the full English name of the country.
    4. 'lat' & 'lng': Provide coordinates for the identified city.
       - IF the city is "Unknown", provide the coordinates for the CAPITAL city of that country.
       - EVEN IF you use capital coordinates, DO NOT write the capital name in the 'city' field if it was unknown.

    Return ONLY a JSON object:
    {{
        "city": "string or Unknown",
        "country": "string",
        "country_name": "string",
        "lat": float,
        "lng": float
    }}
    """
    
    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        return json.loads(response.text)
    except Exception as e:
        print(f"[HATA] Gemini analizi başarısız: {e}")
        return None
    
def main():
    # 1. Mevcut veriyi yükle
    current_data = load_current_data()
    processed_ids = {item["videoId"] for item in current_data}
    
    # 2. YouTube'dan sadece yeni ve uzun (Shorts olmayan) videoları çek
    new_videos = fetch_new_videos(processed_ids)
    
    if not new_videos:
        print("[TAMAM] İşlenecek yeni video yok. Sistem kapatılıyor.")
        return

    # 3. Her yeni videoyu analiz et ve listeye ekle
    updated_count = 0
    for video in reversed(new_videos): # En yeniyi en üste eklemek için tersten işliyoruz
        print(f"[İŞLEM] Analiz ediliyor: {video['title']}")
        
        loc_info = get_location_info_from_gemini(video['title'], video['description'])
        
        if loc_info:
            # Senin 10 haneli JSON yapını tam burada mühürlüyoruz
            new_entry = {
                "videoId": video["videoId"],
                "title": video["title"],
                "publishedAt": video["publishedAt"],
                "thumbnailUrl": video["thumbnailUrl"],
                "city": loc_info["city"],
                "country": loc_info["country"],
                "duration_seconds": video["duration_seconds"],
                "lat": loc_info["lat"],
                "lng": loc_info["lng"],
                "country_name": loc_info["country_name"]
            }
            
            # Yeni videoyu listenin EN BAŞINA ekle
            current_data.insert(0, new_entry)
            updated_count += 1
            print(f"[OK] Yeni video eklendi: {loc_info['city']}, {loc_info['country']}")

    # 4. Dosyayı mühürle ve kaydet
    if updated_count > 0:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(current_data, f, ensure_ascii=False, indent=2)
        print(f"[FİNAL] {updated_count} yeni video başarıyla kaydedildi.")
    else:
        print("[İPTAL] Hiçbir veri kaydedilmedi.")

if __name__ == "__main__":
    main()