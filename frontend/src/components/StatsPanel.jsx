import React, { useMemo, useState } from 'react';
import { createPortal } from 'react-dom';
import { Globe, Map, Clock, Compass, Video, X } from 'lucide-react';

const TOTAL_COUNTRIES = 195;

export default function StatsPanel({ allVideos }) {
  const [open, setOpen] = useState(false);

  const stats = useMemo(() => {
    const uniqueISO3 = new Set(
      allVideos
        .map((v) => String(v.country || '').trim().toUpperCase())
        .filter((c) => /^[A-Z]{3}$/.test(c))
    );
    const countryCount = uniqueISO3.size;
    const countryPct   = ((countryCount / TOTAL_COUNTRIES) * 100).toFixed(1);
    const countryScore = `${countryCount} / ${TOTAL_COUNTRIES} (%${countryPct})`;

    const uniqueCities = new Set(
      allVideos.map((v) => v.city).filter((c) => c && c !== 'Unknown')
    );
    const cityCount = uniqueCities.size;

    const totalSeconds = allVideos.reduce(
      (sum, v) => sum + (Number(v.duration_seconds) || 0), 0
    );
    const days  = Math.floor(totalSeconds / 86400);
    const hours = Math.floor((totalSeconds % 86400) / 3600);
    const archiveStr = `${days} Gün, ${hours} Saat`;

    const videoCount = allVideos.length;

    const latest = allVideos
      .filter((v) => v.publishedAt)
      .sort((a, b) => new Date(b.publishedAt) - new Date(a.publishedAt))[0];
    const lastDiscovery = latest?.country_name || '—';

    return { countryScore, cityCount, archiveStr, videoCount, lastDiscovery };
  }, [allVideos]);

  return (
    <>
      {/* ── MASAÜSTÜ ─────────────────────────────────────────────────────────── */}
      <div className="hidden md:block pointer-events-none select-none w-max">
        <div className="mb-2">
          <h1 className="text-3xl font-bold tracking-tight text-white leading-tight whitespace-nowrap">
            Koparan World Atlas
          </h1>
          <p className="text-[11px] leading-snug mt-0.5 font-medium whitespace-nowrap text-[#ff7a1a]">
            Aynılaşan Dünyada Farklılıkların İzinde
          </p>
        </div>
        <div className="rounded-xl px-3 py-2.5 w-full bg-black/50 backdrop-blur-[16px] border border-white/10 shadow-[0_4px_24px_rgba(0,0,0,0.45)]">
          <StatRow icon={<Globe size={15} />} label="Dünya Keşfi"  value={stats.countryScore} />
          <StatRow icon={<Map   size={15} />} label="Şehir Sayısı" value={`${stats.cityCount} şehir`} />
          <StatRow icon={<Clock size={15} />} label="Toplam Süre"  value={stats.archiveStr} />
          <StatRow icon={<Video size={15} />} label="Video Sayısı" value={`${stats.videoCount} video`} noBorder />
          <div className="mt-2 pt-2 border-t border-white/[0.08]">
            <div className="flex items-center gap-1.5 text-white/40 text-[10px] uppercase tracking-[0.12em] mb-0.5">
              <Compass size={12} />
              Son Keşif
            </div>
            <div className="text-white/85 text-[12px] font-semibold">
              {stats.lastDiscovery}
            </div>
          </div>
        </div>
      </div>

      {/* ── MOBİL: Globe butonu ──────────────────────────────────────────────── */}
      <button
        onClick={() => setOpen(true)}
        aria-label="İstatistikler"
        className="md:hidden fixed bottom-5 left-16 z-10 w-10 h-10 rounded-full
                   bg-black/50 backdrop-blur-[16px] border border-white/10
                   shadow-[0_4px_24px_rgba(0,0,0,0.45)]
                   flex items-center justify-center
                   text-white/55 hover:text-white transition-colors duration-200"
      >
        <Globe size={17} />
      </button>

      {/* ── MOBİL: Portal — ManifestoPanel birebir ikizi ────────────────────── */}
      {open && createPortal(
        <>
          <div
            className="fixed inset-0 z-[100] bg-black/60 backdrop-blur-md"
            onClick={() => setOpen(false)}
          />

          <div className="fixed z-[110] inset-x-4 bottom-[5.5rem] max-w-sm mx-auto
                          rounded-2xl px-5 py-4
                          bg-[rgba(8,12,26,0.93)] backdrop-blur-[28px]
                          border border-white/[0.13]
                          shadow-[0_8px_48px_rgba(0,0,0,0.7)]
                          animate-in fade-in zoom-in-95 duration-200">

            {/* X butonu — daima içeriğin üstünde */}
            <button
              onClick={() => setOpen(false)}
              aria-label="Kapat"
              className="absolute top-3.5 right-3.5 z-[120] text-white/30 hover:text-white/65 transition-colors"
            >
              <X size={15} />
            </button>

            {/* İstatistik satırları — pr-8 ile X alanı boş kalır */}
            <div className="pr-8">
              <MobileStatRow icon={<Globe size={14} />} label="Dünya Keşfi" value={stats.countryScore} />
              <MobileStatRow icon={<Map   size={14} />} label="Şehir"       value={`${stats.cityCount} şehir`} />
              <MobileStatRow icon={<Clock size={14} />} label="Süre"        value={stats.archiveStr} />
              <MobileStatRow icon={<Video size={14} />} label="Video"       value={`${stats.videoCount} video`} last />
            </div>

            {/* Son Keşif — Manifesto imza bölümü gibi */}
            <div className="pt-3 mt-1 border-t border-white/5">
              <div className="flex items-center gap-1.5 text-white/35 text-[10px] uppercase tracking-wider mb-1">
                <Compass size={11} />
                Son Keşif
              </div>
              <p className="text-xs font-light text-white/78 leading-[1.7]">
                {stats.lastDiscovery}
              </p>
            </div>
          </div>
        </>,
        document.body
      )}
    </>
  );
}

/* ── Masaüstü satır bileşeni ─────────────────────────────────────────────── */
function StatRow({ icon, label, value, noBorder = false }) {
  return (
    <div className={['flex items-center justify-between gap-4 py-[7px]', noBorder ? '' : 'border-b border-white/[0.07]'].join(' ')}>
      <div className="flex items-center gap-1.5 text-white/42 text-[11px] uppercase tracking-[0.1em] whitespace-nowrap">
        {icon}
        {label}
      </div>
      <div className="text-white/85 text-[13px] font-medium text-right tabular-nums">
        {value}
      </div>
    </div>
  );
}

/* ── Mobil kart satır bileşeni ───────────────────────────────────────────── */
function MobileStatRow({ icon, label, value, last = false }) {
  return (
    <div className={['flex justify-between items-center py-2', last ? '' : 'border-b border-white/5'].join(' ')}>
      <div className="flex items-center text-[11px] font-bold uppercase tracking-wider text-white/50">
        <span className="text-white/40 mr-2">{icon}</span>
        {label}
      </div>
      <div className="text-[12px] text-white/90 font-medium tabular-nums">
        {value}
      </div>
    </div>
  );
}
