import React, {
  useEffect,
  useRef,
  useState,
  useMemo,
  useCallback,
} from 'react';
import Globe from 'react-globe.gl';
import * as THREE from 'three';

// ── Veri ──────────────────────────────────────────────────────────────────────
const COUNTRIES_URL =
  'https://raw.githubusercontent.com/datasets/geo-boundaries-world-110m/master/countries.geojson';

// Natural Earth GeoJSON'da ISO standardından sapan ülke kodları
const GEOJSON_ISO_OVERRIDES = {
  KOS: 'XKX', // Kosovo
};

// ── Renk sabitleri ─────────────────────────────────────────────────────────────
const BEAM_COLOR          = 'rgba(255, 130, 30, 1.0)';
const BEAM_COLOR_SELECTED = 'rgba(255, 220, 155, 1.0)';
const UNKNOWN_COLOR          = 'rgba(180, 130, 80, 0.28)';
const UNKNOWN_COLOR_SELECTED = 'rgba(220, 180, 120, 0.50)';

/**
 * Sinematik 3D dünya haritası.
 *
 * Props:
 *   locations       – [{ key, lat, lng, city, country (ISO3), videos[] }]
 *   selectedCountry – ISO3 | null
 *   selectedCity    – string | null
 *   onSelectLocation(loc)   – pin tıklaması
 *   onSelectCountry(payload) – polygon tıklaması
 *   isShifted       – sidebar açık mı (canvas yeniden boyutlandırma)
 */
export default function WorldGlobe({
  locations,
  selectedCountry,
  selectedCity,
  onSelectLocation,
  onSelectCountry,
  isShifted,
}) {
  const globeRef     = useRef(null);
  const containerRef = useRef(null);
  const [size, setSize]         = useState({ width: 0, height: 0 });
  const [countries, setCountries] = useState({ features: [] });
  const [hoverPolygon, setHoverPolygon] = useState(null);

  /**
   * Sürükleme takibi.
   * OrbitControls 'start' → isDragging = true
   * OrbitControls 'end'   → isDragging = false
   * Ref kullanıyoruz çünkü render tetiklemesine gerek yok.
   */
  const isDraggingRef = useRef(false);

  /**
   * Dokunmatik ekran tespiti — mount sırasında bir kez değerlendirip ref'e kaydediyoruz.
   * `pointer: coarse` = parmak/stylus; `pointer: fine` = fare.
   * Bu değer session boyunca değişmez, ref yeterli.
   */
  const isTouchDeviceRef = useRef(
    typeof window !== 'undefined' &&
    window.matchMedia('(pointer: coarse)').matches
  );

  // ── GeoJSON yükle ──────────────────────────────────────────────────────────
  useEffect(() => {
    let cancelled = false;
    fetch(COUNTRIES_URL)
      .then((r) => r.json())
      .then((data) => { if (!cancelled) setCountries(data); })
      .catch((err) => console.warn('[WorldGlobe] GeoJSON yüklenemedi:', err));
    return () => { cancelled = true; };
  }, []);

  // ── Container boyutu ───────────────────────────────────────────────────────
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const sync = () => setSize({ width: el.clientWidth, height: el.clientHeight });
    sync();
    const ro = new ResizeObserver(sync);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  useEffect(() => {
    const t = setTimeout(() => {
      const el = containerRef.current;
      if (el) setSize({ width: el.clientWidth, height: el.clientHeight });
    }, 720);
    return () => clearTimeout(t);
  }, [isShifted]);

  // ── Globe hazır: material + damping + sürükleme listener'ları ────────────
  const handleGlobeReady = useCallback(() => {
    const g = globeRef.current;
    if (!g) return;

    const mat = g.globeMaterial();
    mat.color           = new THREE.Color('#060c1a');
    mat.emissive        = new THREE.Color('#0a1f4a');
    mat.emissiveIntensity = 0.26;
    mat.shininess       = 0.5;

    const ctrl = g.controls();
    ctrl.enableDamping = true;
    ctrl.dampingFactor = 0.08;
    ctrl.minDistance   = 180;
    ctrl.maxDistance   = 600;

    // ── Sticky hover düzeltmesi ──────────────────────────────────────────────
    // OrbitControls 'start': kullanıcı dokundu/tıkladı → sürükleme başladı.
    // 'change': kamera hareket ediyor → hover'ı anında sıfırla.
    // 'end': parmak/fare kalktı → isDragging kapat, hover temizle.
    ctrl.addEventListener('start', () => {
      isDraggingRef.current = true;
      setHoverPolygon(null);
    });
    ctrl.addEventListener('change', () => {
      if (isDraggingRef.current) setHoverPolygon(null);
    });
    ctrl.addEventListener('end', () => {
      isDraggingRef.current = false;
      // Parmak kalktığında kalan yapışık hover'ı da temizle
      setHoverPolygon(null);
    });
  }, []);

  // ── İlk yüklenme: 500ms sonra dönüşü başlat + yakınlaş ───────────────────
  useEffect(() => {
    const timer = setTimeout(() => {
      const g = globeRef.current;
      if (!g) return;
      const ctrl = g.controls();
      if (ctrl) {
        ctrl.autoRotate      = true;
        ctrl.autoRotateSpeed = 0.25;
      }
      g.pointOfView({ altitude: 1.7 }, 1500);
    }, 500);
    return () => clearTimeout(timer);
  }, []);

  // ── Seçim değişince DÖN / DUR ─────────────────────────────────────────────
  useEffect(() => {
    const ctrl = globeRef.current?.controls();
    if (!ctrl) return;
    ctrl.autoRotate      = !selectedCountry;
    ctrl.autoRotateSpeed = 0.25;
  }, [selectedCountry]);

  // ── Kamera fly-to ─────────────────────────────────────────────────────────
  const flyTo = useCallback((lat, lng, altitude = 0.9) => {
    const g = globeRef.current;
    if (!g) return;
    g.controls().autoRotate = false;
    g.pointOfView({ 
      lat: clamp(lat, -85, 85), 
      lng, 
      altitude 
    }, 1500);
  }, []);

  // ── Olay işleyiciler ──────────────────────────────────────────────────────

  const handlePointClick = useCallback((point) => {
    flyTo(point.lat, point.lng, 0.8);
    onSelectLocation(point);
  }, [flyTo, onSelectLocation]);

  const handlePolygonClick = useCallback((poly) => {
    if (!poly) return;
    const iso3 = extractIso3(poly);
    if (!iso3) return;
    const name = extractCountryName(poly);
    const c    = centroidOf(poly);
    if (c) flyTo(c.lat, c.lng, 1.35);
    onSelectCountry({ id: iso3, name });
  }, [flyTo, onSelectCountry]);

  /**
   * Polygon hover — iki katmanlı koruma:
   *
   * 1. Dokunmatik ekran (pointer: coarse): hover tamamen devre dışı.
   *    Mobilde sadece tıklama (onPolygonClick) Sidebar'ı açar;
   *    sürükleme/parmak kaldırma hiçbir görsel iz bırakmaz.
   *
   * 2. Sürükleme guard: fare ile kullanımda da sürükleme sırasında
   *    hover güncellenmez (isDraggingRef).
   */
  const handlePolygonHover = useCallback((poly) => {
    // Kural 1 — dokunmatik cihaz: hover yok
    if (isTouchDeviceRef.current) {
      if (hoverPolygon !== null) setHoverPolygon(null);
      return;
    }
    // Kural 2 — fare ile sürükleme
    if (isDraggingRef.current) {
      setHoverPolygon(null);
      return;
    }
    setHoverPolygon(poly);
  }, [hoverPolygon]);

  // ── Türetilen veriler ─────────────────────────────────────────────────────
  const selectedCountryIso3 = canonicalCountry(selectedCountry);

  const visitedIso3s = useMemo(
    () => new Set(locations.map((l) => canonicalCountry(l.country)).filter(Boolean)),
    [locations],
  );

  const pointsData = useMemo(
    () => locations.map((l) => ({
      ...l,
      isUnknown: !l.city || l.city.toLowerCase() === 'unknown',
    })),
    [locations],
  );

  const rings = useMemo(() => locations.map((l) => {
    const locIso       = canonicalCountry(l.country);
    const countryMatch = selectedCountryIso3 && locIso === selectedCountryIso3;
    const cityMatch    = !selectedCity || normalize(l.city) === normalize(selectedCity);
    const isUnknown    = !l.city || l.city.toLowerCase() === 'unknown';
    return {
      lat: l.lat,
      lng: l.lng,
      isSelected: Boolean(countryMatch && cityMatch),
      isUnknown,
    };
  }), [locations, selectedCountryIso3, selectedCity]);

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div
      ref={containerRef}
      className="relative w-full h-full"
      style={{ background: 'radial-gradient(ellipse at center, #0a1229 0%, #05070d 60%, #000 100%)' }}
      // pointerDown: anında temizle
      onPointerDown={() => setHoverPolygon(null)}
      // pointerUp: 50ms gecikmeli temizle — tıklama işlemi tamamlandıktan
      // sonra kalan her türlü hover artığını garantiyle sıfırlar
      onPointerUp={() => setTimeout(() => setHoverPolygon(null), 150)}
    >
      {size.width > 0 && size.height > 0 && (
        <Globe
          ref={globeRef}
          width={size.width}
          height={size.height}
          backgroundColor="rgba(0,0,0,0)"
          showAtmosphere
          atmosphereColor="#1a55ff"
          atmosphereAltitude={0.20}
          onGlobeReady={handleGlobeReady}

          polygonsData={countries.features}
          polygonAltitude={(d) => {
            const iso = extractIso3(d);
            if (iso && iso === selectedCountryIso3) return 0.015;
            if (d === hoverPolygon) return 0.008;
            return 0.003;
          }}
          polygonCapColor={(d) => {
            const iso     = extractIso3(d);
            const visited = iso && visitedIso3s.has(iso);
            if (iso && iso === selectedCountryIso3) return 'rgba(255, 122, 26, 0.42)';
            if (d === hoverPolygon && visited)       return 'rgba(160, 230, 255, 0.28)';
            if (visited)                             return 'rgba(0, 150, 255, 0.15)';
            if (d === hoverPolygon)                  return '#2a2a2e';
            return '#1e2124';
          }}
          polygonSideColor={() => 'rgba(20, 60, 120, 0.10)'}
          polygonStrokeColor={(d) => {
            const iso = extractIso3(d);
            if (iso && iso === selectedCountryIso3) return 'rgba(255, 190, 100, 0.95)';
            if (d === hoverPolygon)                 return 'rgba(140, 220, 255, 0.75)';
            if (iso && visitedIso3s.has(iso))       return 'rgba(60, 160, 255, 0.35)';
            return 'rgba(255, 255, 255, 0.07)';
          }}
          polygonStrokeWidth={0.5}
          polygonLabel={(d) => {
            const name = extractCountryName(d) || '';
            const iso  = extractIso3(d);
            return `<div style="font-family:Inter,system-ui,sans-serif;font-size:12px;padding:6px 10px;
                      background:rgba(10,15,31,0.9);border:1px solid rgba(255,122,26,0.45);
                      border-radius:6px;color:#ffe1c8;">
                      ${escapeHtml(name)}
                      ${iso ? `<span style="opacity:0.55;margin-left:6px;font-size:10px;">${escapeHtml(iso)}</span>` : ''}
                    </div>`;
          }}
          onPolygonHover={handlePolygonHover}
          onPolygonClick={handlePolygonClick}

          ringsData={rings}
          ringColor={(r) => (t) => {
            if (r.isUnknown)  return `rgba(180, 130, 80, ${0.22 * (1 - t)})`;
            if (r.isSelected) return `rgba(255, 200, 130, ${1 - t})`;
            return `rgba(255, 122, 26, ${0.85 - t * 0.85})`;
          }}
          ringMaxRadius={(r) => r.isUnknown ? 5.5 : r.isSelected ? 4.8 : 2.5}
          ringPropagationSpeed={(r) => r.isUnknown ? 0.55 : r.isSelected ? 2.8 : 1.4}
          ringRepeatPeriod={(r) => r.isUnknown ? 4000 : r.isSelected ? 900 : 1800}
          ringAltitude={0.0025}

          pointsData={pointsData}
          pointLat="lat"
          pointLng="lng"
          pointAltitude={0.02}
          pointRadius={(d) => {
            if (d.isUnknown) return 0.045;
            return Math.max(0.028, Math.sqrt(d.videos?.length ?? 1) * 0.032);
          }}
          pointResolution={12}
          pointColor={(d) => {
            const locIso      = canonicalCountry(d.country);
            const countryMatch = selectedCountryIso3 && locIso === selectedCountryIso3;
            const cityMatch    = !selectedCity || normalize(d.city) === normalize(selectedCity);
            const isActive     = countryMatch && cityMatch;
            if (d.isUnknown) return isActive ? UNKNOWN_COLOR_SELECTED : UNKNOWN_COLOR;
            return isActive ? BEAM_COLOR_SELECTED : BEAM_COLOR;
          }}
          pointLabel={(d) => `
            <div style="font-family:Inter,system-ui,sans-serif;font-size:12px;padding:6px 10px;
              background:rgba(10,15,31,0.92);border:1px solid rgba(255,122,26,0.6);
              border-radius:6px;color:#fff;box-shadow:0 0 14px rgba(255,122,26,0.4);">
              <div style="color:#ff7a1a;font-weight:600;">
                ${escapeHtml(d.city ?? '')}${d.country && d.country !== d.city ? ', ' + escapeHtml(d.country) : ''}
              </div>
              <div style="color:#c6d2e8;margin-top:2px;">${d.videos?.length ?? 0} video</div>
            </div>`}
          onPointClick={handlePointClick}
        />
      )}

      <div className="pointer-events-none absolute bottom-5 right-6 text-[11px] text-white/40 tracking-wide">
        Halka veya ülke tıkla · sürükle · kaydır
      </div>
    </div>
  );
}

// ── Yardımcılar ───────────────────────────────────────────────────────────────

function clamp(v, lo, hi) {
  return Math.min(Math.max(v, lo), hi);
}

function escapeHtml(s) {
  return String(s || '')
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

/** Şehir karşılaştırması için string normalize. */
export function normalize(s) {
  if (!s) return '';
  return String(s).trim().toLowerCase()
    .replace(/[.,()'`\-]/g, ' ').replace(/\s+/g, ' ').trim();
}

/** ISO Alpha-3 doğrulama: geçerliyse uppercase döner, değilse ''. */
export function canonicalCountry(iso3) {
  if (iso3 == null) return '';
  const s = String(iso3).trim().toUpperCase();
  return /^[A-Z]{3}$/.test(s) ? s : '';
}

/** Polygon feature'dan görsel ülke adı çıkartır. */
function extractCountryName(feature) {
  if (!feature?.properties) return '';
  const p = feature.properties;
  return p.ADMIN || p.admin || p.NAME || p.name || p.NAME_LONG || p.name_long || p.SOVEREIGNT || '';
}

/**
 * Polygon feature'dan ISO Alpha-3 kodu çıkartır.
 * Sıra: ISO_A3 → iso_a3 → ADM0_A3 → adm0_a3 → WB_A3 → wb_a3
 */
function extractIso3(feature) {
  if (!feature?.properties) return '';
  const p = feature.properties;
  for (const cand of [p.ISO_A3, p.iso_a3, p.ADM0_A3, p.adm0_a3, p.WB_A3, p.wb_a3]) {
    if (!cand) continue;
    const code = String(cand).trim().toUpperCase();
    if (!/^[A-Z]{3}$/.test(code)) continue;
    return GEOJSON_ISO_OVERRIDES[code] || code;
  }
  return '';
}

/** Polygon'un yaklaşık merkez koordinatını hesaplar. */
function centroidOf(feature) {
  try {
    const geom = feature?.geometry;
    if (!geom) return null;
    const rings =
      geom.type === 'Polygon'      ? [geom.coordinates[0]] :
      geom.type === 'MultiPolygon' ? geom.coordinates.map((p) => p[0]) : [];
    let sumLat = 0, sumLng = 0, n = 0;
    for (const ring of rings) {
      for (const [lng, lat] of ring) { sumLat += lat; sumLng += lng; n++; }
    }
    return n === 0 ? null : { lat: sumLat / n, lng: sumLng / n };
  } catch {
    return null;
  }
}
