import React, { useMemo, useState, useCallback, useRef, useEffect } from 'react';
import WorldGlobe, {
  normalize,
  canonicalCountry,
} from './components/WorldGlobe.jsx';
import Sidebar from './components/Sidebar.jsx';
import rawVideos from './data/final_map_with_coords.json';
import StatsPanel from './components/StatsPanel.jsx';
import ManifestoPanel from './components/ManifestoPanel.jsx';

/* ── Veri hazırlama ────────────────────────────────────────────────────────── */

function groupByLocation(videos) {
  const map = new Map();
  for (const v of videos) {
    if (v.lat == null || v.lng == null) continue;
    const key = `${Number(v.lat).toFixed(4)},${Number(v.lng).toFixed(4)}`;
    if (!map.has(key)) {
      map.set(key, {
        key,
        lat: Number(v.lat),
        lng: Number(v.lng),
        city: v.city || 'Unknown',
        country: v.country || 'Unknown',
        country_name: v.country_name || '',
        videos: [],
      });
    }
    map.get(key).videos.push(v);
  }
  return Array.from(map.values());
}

function byDateDesc(a, b) {
  return new Date(b.publishedAt || 0).getTime() - new Date(a.publishedAt || 0).getTime();
}

function groupByCity(list) {
  const m = new Map();
  for (const v of list) {
    const key = v.city && v.city !== 'Unknown' ? v.city : '— Şehir yok —';
    if (!m.has(key)) m.set(key, []);
    m.get(key).push(v);
  }
  return Array.from(m.entries()).map(([city, videos]) => ({
    city,
    videos: [...videos].sort(byDateDesc),
  }));
}

/**
 * Ülkeye göre gruplama.
 * null  → seçim yok (çağrıcı buildAllGroups kullanmalı)
 * []    → ülkede video yok (kesinlikle fallback yapma)
 */
function buildGroups(allVideos, selection) {
  if (!selection?.country) return null;

  const wantIso3 = canonicalCountry(selection.country);
  if (!wantIso3) return [];

  const inCountry = allVideos.filter(
    (v) => canonicalCountry(v.country) === wantIso3
  );
  if (inCountry.length === 0) return [];

  if (selection.city) {
    const wantCity = normalize(selection.city);
    const primary  = inCountry.filter((v) => normalize(v.city) === wantCity).sort(byDateDesc);
    const rest     = groupByCity(inCountry.filter((v) => normalize(v.city) !== wantCity))
                       .sort((a, b) => b.videos.length - a.videos.length);
    const groups = [];
    if (primary.length > 0) groups.push({ city: selection.city, videos: primary, primary: true });
    groups.push(...rest);
    return groups;
  }

  return groupByCity(inCountry).sort((a, b) => b.videos.length - a.videos.length);
}

function buildAllGroups(allVideos) {
  return groupByCity([...allVideos].sort(byDateDesc)).sort(
    (a, b) => b.videos.length - a.videos.length
  );
}

/* ── Component ─────────────────────────────────────────────────────────────── */

export default function App() {
  const locations = useMemo(() => groupByLocation(rawVideos), []);

  /**
   * selection = {
   *   country: 'MNG',          // ISO3
   *   countryName: 'Mongolia', // GeoJSON'dan gelen tam ad
   *   city: string | null
   * } | null
   */
  const [selection, setSelection]   = useState(null);
  const [selectionNonce, setSelectionNonce] = useState(0);

  const bump = useRef(0);
  const bumpNonce = useCallback(() => {
    bump.current += 1;
    setSelectionNonce(bump.current);
  }, []);

  // Pin tıklaması
  const handleSelectLocation = useCallback((loc) => {
    const iso3 = canonicalCountry(loc.country);
    if (!iso3) return;
    setSelection({
      country: iso3,
      countryName: loc.country_name || iso3,
      city: loc.city && loc.city !== 'Unknown' ? loc.city : null,
    });
    bumpNonce();
  }, [bumpNonce]);

  // Polygon tıklaması — WorldGlobe { id, name } gönderir
  const handleSelectCountry = useCallback((p) => {
    const iso3 = canonicalCountry(p.id);
    if (!iso3) return;
    setSelection({ country: iso3, countryName: p.name || iso3, city: null });
    bumpNonce();
  }, [bumpNonce]);

  const handleClose = useCallback(() => setSelection(null), []);

  // Gruplar
  const groups = useMemo(() => {
    const result = buildGroups(rawVideos, selection);
    return result === null ? buildAllGroups(rawVideos) : result;
  }, [selection]);

  const isOpen       = Boolean(selection);
  const countryLabel = selection?.countryName || selection?.country || '';

  useEffect(() => {
    if (!selection) return;
    const total = groups.reduce((acc, g) => acc + g.videos.length, 0);
    console.log(
      `[App] ${selection.country} "${selection.countryName}" city=${selection.city || '—'} → ${total} video`
    );
  }, [selection, groups]);

  /* Sidebar'a geçilen ortak props */
  const sidebarProps = {
    country: countryLabel,
    selectedCity: selection?.city ?? null,
    groups,
    countrySelected: Boolean(selection),
    scrollNonce: selectionNonce,
    onClose: handleClose,
  };

  return (
    <div className="flex w-screen h-screen bg-space-900 text-white overflow-hidden">

      {/* ── GLOBE ─────────────────────────────────────────────────────────────
          Mobilde her zaman tam genişlik; masaüstünde sidebar açılınca %62.
      ────────────────────────────────────────────────────────────────────── */}
      <div
        className={[
          'relative h-full transition-[width] duration-700 ease-in-out',
          'w-full',
          isOpen ? 'md:w-[62%]' : 'md:w-full',
        ].join(' ')}
      >
        <WorldGlobe
          locations={locations}
          selectedCountry={selection?.country ?? null}
          selectedCity={selection?.city ?? null}
          onSelectLocation={handleSelectLocation}
          onSelectCountry={handleSelectCountry}
          isShifted={isOpen}
        />

        {/* Stats — z-10; mobil buton pointer-events-auto StatsPanel içinde */}
        <div className="absolute top-6 left-8 z-10">
          <StatsPanel allVideos={rawVideos} />
        </div>
      </div>

      {/* Manifesto — fixed, kendi z-10'unu yönetiyor */}
      <ManifestoPanel />

      {/* ── MOBİL: üst orta başlık ────────────────────────────────────────────
          Sadece mobilde görünür (md:hidden). pointer-events-none → harita
          sürüklemeyi engellemez. Tüm katmanların üzerinde (z-50).
      ────────────────────────────────────────────────────────────────────── */}
      <div className="md:hidden fixed top-10 inset-x-0 z-[30] flex flex-col items-center pointer-events-none select-none">
        <h1
          className="font-black tracking-[0.2em] text-base text-white uppercase"
          style={{ textShadow: '0 0 18px rgba(255,122,26,0.75), 0 0 6px rgba(255,122,26,0.45)' }}
        >
          KOPARAN WORLD ATLAS
        </h1>
        <p className="text-[9px] italic text-white/70 mt-2 mb-4">
          Aynılaşan dünyada farklılıkların izinde.
        </p>
      </div>

      {/* ── MASAÜSTÜ SIDEBAR (flex child) ─────────────────────────────────── */}
      <div
        className={[
          'hidden md:block h-full bg-space-800/90 backdrop-blur-md border-l border-white/5',
          'transition-[width] duration-700 ease-in-out overflow-hidden flex-shrink-0',
          isOpen ? 'w-[38%]' : 'w-0',
        ].join(' ')}
      >
        {isOpen && <Sidebar {...sidebarProps} />}
      </div>

      {/* ── MOBİL: backdrop ───────────────────────────────────────────────────
          z-[19] → bottom-sheet (z-20) altında, diğer UI (z-10) üstünde.
          Tıklanınca sidebar kapanır.
      ────────────────────────────────────────────────────────────────────── */}
      <div
        className={[
          'md:hidden fixed inset-0 z-[19] bg-black/45 backdrop-blur-[4px]',
          'transition-opacity duration-500',
          isOpen ? 'opacity-100 pointer-events-auto' : 'opacity-0 pointer-events-none',
        ].join(' ')}
        onClick={handleClose}
      />

      {/* ── MOBİL: bottom-sheet sidebar ───────────────────────────────────────
          Açılınca transform: translateY(0), kapanınca translateY(100%).
          Sheet her zaman DOM'da; içerik sadece isOpen iken mount edilir.
      ────────────────────────────────────────────────────────────────────── */}
      <div
        className={[
          'md:hidden fixed bottom-0 inset-x-0 z-20',
          'h-[82vh] bg-space-800/95 backdrop-blur-[20px]',
          'rounded-t-2xl border-t border-white/[0.12]',
          'shadow-[0_-8px_40px_rgba(0,0,0,0.55)]',
          'transition-transform duration-500 ease-[cubic-bezier(0.32,0.72,0,1)]',
          isOpen ? 'translate-y-0' : 'translate-y-full',
        ].join(' ')}
      >
        {isOpen && <Sidebar {...sidebarProps} showHandle />}
      </div>
    </div>
  );
}
