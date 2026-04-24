# 🌍 Koparan World Atlas

> *Aynılaşan Dünyada Farklılıkların İzinde*

Seyahat YouTuber'ı **Muhammet Fatih Koparan**'ın kanalındaki tüm videoları, interaktif bir 3D dünya küresi üzerinde haritalayan açık kaynaklı bir proje. Her gece GitHub Actions ile otomatik olarak güncellenir; yeni video yayınlanır yayınlanmaz haritaya işlenir.

**[→ Canlı Demo](https://koparan-world-atlas.vercel.app)**

---

## Ekran Görüntüleri

| Masaüstü | Mobil |
|---|---|
| 3D küre + sağ panel | Alt bar + yüzen kartlar |

---

## Nasıl Çalışır?

```
YouTube Kanalı
      │
      ▼  (Her gece 03:00 TR — GitHub Actions)
  YouTube Data API v3
      │  Son 5 video çekilir, Shorts (< 60sn) elenir
      ▼
  Google Gemini API
      │  Başlık + açıklama → şehir / ülke / koordinat
      ▼
  final_map_with_coords.json  ←──── git commit & push
      │
      ▼  (Vercel otomatik deploy)
  3D Globe Görselleştirmesi
```

Hiçbir manuel adım yok. Video çıkar, harita güncellenir.

---

## Özellikler

- **3D Dönen Küre** — `react-globe.gl` (Three.js) ile sinematik dark tema
- **Ülke Poligonları** — 195 ülkenin sınırları; ziyaret edilenler turuncu vurguyla öne çıkar
- **Neon Pinler** — Her şehir için nabız atan halkalar
- **Ülkeye Tıklama** — Seçilen ülkenin videoları sağ panelde listelenir (thumbnail, başlık, tarih, süre, YouTube linki)
- **İstatistik Paneli** — Keşfedilen ülke/şehir sayısı, toplam içerik süresi, son keşif
- **Manifesto Paneli** — Projenin ruhu ve kanal linkleri
- **Tam Mobil Desteği** — Alt bar butonları, yüzen glassmorphism kartlar, bottom-sheet sidebar
- **Otomatik Veri Güncelleme** — GitHub Actions pipeline, her gece kanalı tarar

---

## Veri

`frontend/src/data/final_map_with_coords.json` içindeki her kayıt:

```json
{
  "videoId": "1f1x5pBAsOQ",
  "title": "22 Yıldır Bu Sokakta Çalışıyorum - Dominik",
  "publishedAt": "2026-04-19T08:54:46Z",
  "thumbnailUrl": "https://i.ytimg.com/vi/.../maxresdefault.jpg",
  "city": "Santo Domingo",
  "country": "DOM",
  "country_name": "Dominican Republic",
  "lat": 18.4713858,
  "lng": -69.8918436,
  "duration_seconds": 2187
}
```

**Güncel Rakamlar**

| | |
|---|---|
| Toplam Video | 449 |
| Keşfedilen Ülke | 54 / 195 |
| Keşfedilen Şehir | 186 |
| Toplam İçerik | ~246 saat |

---

## Teknoloji Stack

| Katman | Teknoloji |
|---|---|
| Frontend | React 18 + Vite |
| Stil | Tailwind CSS |
| 3D Küre | react-globe.gl (Three.js) |
| İkonlar | lucide-react |
| Otomasyon | GitHub Actions |
| Veri Kaynağı | YouTube Data API v3 |
| Konum Tespiti | Google Gemini API |
| Deploy | Vercel |

---

## Proje Yapısı

```
koparan-world-atlas/
├── .github/
│   └── workflows/
│       └── main.yml              # Günlük otomatik güncelleme
├── scripts/
│   └── update_map.py             # Ana pipeline: YouTube → Gemini → JSON
├── frontend/
│   ├── index.html
│   ├── vite.config.js
│   ├── tailwind.config.js
│   └── src/
│       ├── App.jsx               # Ana layout, state yönetimi
│       ├── components/
│       │   ├── WorldGlobe.jsx    # 3D küre, polygon/pin katmanları
│       │   ├── Sidebar.jsx       # Video listesi paneli
│       │   ├── StatsPanel.jsx    # İstatistik widget'ı
│       │   └── ManifestoPanel.jsx# Proje açıklaması + linkler
│       └── data/
│           └── final_map_with_coords.json  # Ana veri dosyası
└── requirements.txt              # Python bağımlılıkları
```

---

## Kurulum (Yerel Geliştirme)

### Gereksinimler

- Node.js ≥ 18
- Python ≥ 3.10
- YouTube Data API v3 anahtarı
- Google Gemini API anahtarı

### Frontend

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173
npm run build      # Production build
```

### Otomasyon Scripti

```bash
# Kök dizinde .env dosyası oluştur:
YOUTUBE_API_KEY=your_key_here
GEMINI_API_KEY=your_key_here

# Bağımlılıkları kur:
pip install -r requirements.txt

# Scripti elle çalıştır:
python scripts/update_map.py
```

---

## GitHub Actions Kurulumu

Repo → **Settings → Secrets and variables → Actions** altına şu iki secret'ı ekle:

| Secret | Açıklama |
|---|---|
| `YOUTUBE_API_KEY` | Google Cloud Console'dan alınan YouTube Data API v3 anahtarı |
| `GEMINI_API_KEY` | Google AI Studio'dan alınan Gemini API anahtarı |

Pipeline her gece **00:00 UTC** (Türkiye saatiyle **03:00**) otomatik çalışır. **Actions** sekmesindeki **"Run workflow"** butonu ile elle de tetiklenebilir.

### Pipeline Adımları

1. Kanalın son 5 videosu çekilir
2. Daha önce işlenmiş videolar (`videoId` kontrolü) ve Shorts (< 60 saniye) elenir
3. Her yeni video için Gemini API'ya başlık + açıklama gönderilir → şehir, ülke (ISO 3166-1 alpha-3), koordinat alınır
4. `final_map_with_coords.json` başına yeni kayıt eklenir
5. Değişiklik varsa otomatik commit + push yapılır
6. Vercel yeni commit'i algılar ve siteyi deploy eder

---

## Vercel Deploy

`frontend/` klasörü Vercel'e bağlıdır. Ayarlar:

| | |
|---|---|
| **Framework Preset** | Vite |
| **Root Directory** | `frontend` |
| **Build Command** | `npm run build` |
| **Output Directory** | `dist` |

---

## Katkı

Bu proje kişisel bir sevgi projesi. Hata bildirimi veya öneri için Issues açabilirsin.

---

## Teşekkür

Dünyayı sadece gidilen yerler olarak değil, yaşanan hikâyeler olarak gösteren; her karesiyle sadece yeni yerler değil, aynı zamanda öğrencilere umut ve gelecek sunan **Fatih Koparan**'a, topluma değer katan bu büyük emeği için sonsuz teşekkürler.

*— Muhammet Vefa Yoksul*
