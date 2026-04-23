# Koparan Map — Frontend

Vite + React + Tailwind tabanlı 3D globe görselleştirmesi.

## Teknoloji Stack

- **Vite** + **React 18**
- **Tailwind CSS** (cinematic dark tema)
- **react-globe.gl** (Three.js tabanlı 3D globe)
- **lucide-react** (ikonlar)

## Kurulum

`frontend/` klasörünün içindeyken:

```bash
# 1) Bağımlılıkları kur
npm install

# (Eğer paketler manuel olarak kurulacaksa:)
npm install react-globe.gl three lucide-react
npm install -D vite @vitejs/plugin-react tailwindcss postcss autoprefixer

# 2) Geliştirme sunucusunu başlat
npm run dev

# 3) Production build
npm run build
npm run preview
```

## Veri Kaynağı

`src/App.jsx` dosyası veriyi şu yoldan import eder:

```
../../scripts/data/final_map_with_coords.json
```

Yani proje yapısı şu şekilde olmalı:

```
koparan-map/
├── scripts/
│   └── data/
│       └── final_map_with_coords.json   ← Python pipeline'ın çıktısı
└── frontend/
    ├── src/
    │   ├── App.jsx
    │   └── components/
    └── ...
```

> Not: Eğer Python scriptleriniz veriyi `koparan-map/data/` altına kaydediyorsa,
> ya dosyayı `scripts/data/` altına kopyalayın ya da `src/App.jsx` içindeki
> import satırını `'../../data/final_map_with_coords.json'` olarak güncelleyin.

## Özellikler

- **Cinematic Dark** — Koyu dünya yüzeyi + mavi atmosfer parıltısı.
- **Ülke Sınırları** — `countries.geojson` (110m) ile belirgin siyasi sınırlar;
  hover'da ülke turuncu ton ile vurgulanıyor.
- **Neon Pinler** — Parlayan turuncu pinler + sürekli nabız atan glow halkaları.
- **Fly-To** — Pine/ülkeye tıklayınca kamera 1.5sn'de yumuşak zoom yapıyor.
- **Shifting Sidebar** — Sağdan açılan panel; globe canvas'ı yeniden boyutlanıp
  sola kayar (overlay DEĞİL, gerçek bir layout sıkışması).
- **Şık Kartlar** — Sidebar'da thumbnail, başlık, tarih, süre ve YouTube linki.

## Özelleştirme

- Ana renkler `tailwind.config.js` içindeki `neon` ve `space` paletlerinde.
- Globe'un dark material ayarları `components/WorldGlobe.jsx` içinde
  `globeMaterial()` çağrısında.
- Ülke sınır GeoJSON URL'i yine `WorldGlobe.jsx` üst kısmında (`COUNTRIES_URL`).
