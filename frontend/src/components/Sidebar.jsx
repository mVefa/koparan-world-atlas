import React, { useEffect, useRef } from 'react';
import { X, MapPin, Play, Clock } from 'lucide-react';

/**
 * Sağdan açılan panel (masaüstü) / aşağıdan açılan bottom-sheet (mobil).
 *
 * Props:
 *   - country: string             (seçili ülkenin tam adı)
 *   - selectedCity: string|null
 *   - groups: [{ city, videos, primary? }]
 *   - countrySelected: boolean
 *   - scrollNonce: number
 *   - onClose(): void
 *   - showHandle: boolean         (mobil bottom-sheet için tutamaç çizgisi)
 */
export default function Sidebar({
  country,
  selectedCity,
  groups,
  countrySelected,
  scrollNonce,
  onClose,
  showHandle = false,
}) {
  const totalVideos = groups.reduce((acc, g) => acc + g.videos.length, 0);

  const listRef    = useRef(null);
  const primaryRef = useRef(null);

  useEffect(() => {
    const t = window.setTimeout(() => {
      if (primaryRef.current) {
        primaryRef.current.scrollIntoView({ behavior: 'smooth', block: 'start' });
      } else if (listRef.current) {
        listRef.current.scrollTo({ top: 0, behavior: 'smooth' });
      }
    }, 60);
    return () => window.clearTimeout(t);
  }, [scrollNonce, selectedCity, country]);

  const isEmpty = countrySelected && groups.length === 0;

  return (
    <aside className="h-full w-full flex flex-col text-white">

      {/* ── Mobil tutamaç (handle) ────────────────────────────────────────────── */}
      {showHandle && (
        <div className="flex justify-center pt-3 pb-1 flex-shrink-0">
          <div className="w-10 h-[3px] rounded-full bg-white/20" />
        </div>
      )}

      {/* ── Header ───────────────────────────────────────────────────────────── */}
      <header className="px-6 pt-5 pb-4 border-b border-white/10 flex items-start justify-between gap-4 flex-shrink-0">
        <div className="min-w-0">
          <div className="flex items-center gap-2 text-neon-orange">
            <MapPin size={16} strokeWidth={2.2} />
            <span className="uppercase tracking-[0.3em] text-xs font-medium">
              {selectedCity ? 'Şehir' : 'Ülke'}
            </span>
          </div>
          <h2 className="mt-2 text-2xl font-semibold leading-tight truncate">
            {selectedCity || country}
          </h2>
          {selectedCity && (
            <p className="text-sm text-white/60 mt-0.5 truncate">{country}</p>
          )}
          {!isEmpty && (
            <p className="text-xs text-white/40 mt-2">
              {totalVideos} video · {groups.length} şehir
            </p>
          )}
        </div>

        <button
          onClick={onClose}
          aria-label="Kapat"
          className="p-2 rounded-full bg-white/5 hover:bg-white/10 transition-colors text-white/80 hover:text-white flex-shrink-0"
        >
          <X size={18} />
        </button>
      </header>

      {/* ── İçerik ───────────────────────────────────────────────────────────── */}
      {isEmpty ? (
        /* Boş durum */
        <div className="flex-1 flex flex-col items-center justify-center gap-4 px-8 text-center">
          <div className="w-14 h-14 rounded-full bg-white/[0.04] border border-white/[0.07] grid place-items-center">
            <MapPin size={22} className="text-white/25" strokeWidth={1.5} />
          </div>
          <p className="text-sm text-white/35 leading-relaxed max-w-[220px]">
            Bu ülkede henüz bir video bulunmuyor.
          </p>
        </div>
      ) : (
        /* Video listesi */
        <div
          ref={listRef}
          className="flex-1 overflow-y-auto scrollbar-thin px-5 py-4 space-y-6"
        >
          {groups.map((g) => (
            <CityGroup
              key={g.city}
              group={g}
              anchorRef={g.primary ? primaryRef : null}
            />
          ))}
        </div>
      )}
    </aside>
  );
}

function CityGroup({ group, anchorRef }) {
  const { city, videos, primary } = group;

  return (
    <section ref={anchorRef} className="scroll-mt-4">
      <header className="flex items-center justify-between mb-2">
        <h3
          className={[
            'text-[11px] uppercase tracking-[0.25em] font-medium',
            primary ? 'text-neon-orange' : 'text-white/55',
          ].join(' ')}
        >
          {city}
        </h3>
        <span className="text-[11px] text-white/40">{videos.length}</span>
      </header>

      <div
        className={[
          'h-px mb-3',
          primary ? 'bg-neon-orange/40' : 'bg-white/5',
        ].join(' ')}
      />

      <div className="space-y-2">
        {videos.map((v) => (
          <VideoCard key={v.videoId} video={v} />
        ))}
      </div>
    </section>
  );
}

function VideoCard({ video }) {
  const { videoId, title, thumbnailUrl, publishedAt, duration_seconds } = video;
  const url = `https://www.youtube.com/watch?v=${videoId}`;

  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      className="group flex gap-3 p-2.5 rounded-lg bg-white/[0.03] hover:bg-white/[0.07]
                 border border-white/5 hover:border-neon-orange/60
                 transition-all duration-200 hover:shadow-neon-orange"
    >
      {/* Thumbnail */}
      <div className="relative w-28 h-[63px] flex-shrink-0 rounded-md overflow-hidden bg-black">
        {thumbnailUrl ? (
          <img
            src={thumbnailUrl}
            alt={title}
            loading="lazy"
            className="w-full h-full object-cover group-hover:scale-[1.04] transition-transform duration-300"
          />
        ) : (
          <div className="w-full h-full grid place-items-center text-white/30 text-[10px]">
            no thumb
          </div>
        )}

        {Number.isFinite(duration_seconds) && (
          <span className="absolute bottom-1 right-1 px-1.5 py-[1px] rounded-sm bg-black/80 text-[10px] font-medium text-white/90">
            {formatDuration(duration_seconds)}
          </span>
        )}

        <div className="absolute inset-0 grid place-items-center opacity-0 group-hover:opacity-100 transition-opacity bg-black/25">
          <div className="w-8 h-8 rounded-full bg-neon-orange/90 grid place-items-center shadow-neon-orange">
            <Play size={12} className="text-black fill-black translate-x-[1px]" />
          </div>
        </div>
      </div>

      {/* Meta */}
      <div className="flex-1 min-w-0">
        <h4 className="text-[13px] font-medium text-white/95 leading-snug line-clamp-2 group-hover:text-neon-orangeGlow transition-colors">
          {title}
        </h4>
        <div className="mt-1.5 flex items-center gap-2 text-[11px] text-white/45">
          {publishedAt && <span>{formatDate(publishedAt)}</span>}
          {Number.isFinite(duration_seconds) && (
            <>
              <span className="opacity-40">•</span>
              <span className="inline-flex items-center gap-1">
                <Clock size={10} />
                {formatDuration(duration_seconds)}
              </span>
            </>
          )}
        </div>
      </div>
    </a>
  );
}

/* ── Formatlayıcılar ─────────────────────────────────────────────────────── */
function formatDate(iso) {
  try {
    return new Date(iso).toLocaleDateString('tr-TR', {
      year: 'numeric', month: 'short', day: '2-digit',
    });
  } catch { return ''; }
}

function formatDuration(totalSec) {
  const s   = Math.max(0, Math.round(totalSec));
  const h   = Math.floor(s / 3600);
  const m   = Math.floor((s % 3600) / 60);
  const ss  = s % 60;
  const pad = (n) => String(n).padStart(2, '0');
  return h > 0 ? `${h}:${pad(m)}:${pad(ss)}` : `${m}:${pad(ss)}`;
}
