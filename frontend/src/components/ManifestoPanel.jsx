import React, { useState } from 'react';
import { createPortal } from 'react-dom';
import { Youtube, Github, Info, X } from 'lucide-react';

const MANIFESTO =
  'Dünyayı sadece gidilen yerler olarak değil, yaşanan hikâyeler olarak gösteren; her karesiyle sadece yeni yerler değil, aynı zamanda öğrencilere umut ve gelecek sunan Fatih Koparan\'a, topluma değer katan bu büyük emeği için sonsuz teşekkürler.';

const LINKS = [
  { href: 'https://www.youtube.com/@ifkoparan', icon: <Youtube size={17} />, label: 'YouTube' },
  { href: 'https://github.com/mVefa',           icon: <Github  size={17} />, label: 'GitHub'  },
];

export default function ManifestoPanel() {
  const [open, setOpen] = useState(false);

  return (
    <>
      {/* ── Mobil: yuvarlak Info butonu ──────────────────────────────────────── */}
      <button
        onClick={() => setOpen(true)}
        aria-label="Hakkında"
        className="md:hidden fixed bottom-5 left-5 z-10 w-10 h-10 rounded-full
                   bg-black/50 backdrop-blur-[16px] border border-white/10
                   shadow-[0_4px_24px_rgba(0,0,0,0.45)]
                   flex items-center justify-center
                   text-white/55 hover:text-white transition-colors duration-200"
      >
        <Info size={16} />
      </button>

      {/* ── Mobil: Portal ile body'ye render — stacking context kırılır ─────── */}
      {open && createPortal(
        <>
          {/* Backdrop z-[100]: küreyi ve başlığı (z-[30]) tamamen örter */}
          <div
            className="fixed inset-0 z-[100] bg-black/60 backdrop-blur-md"
            onClick={() => setOpen(false)}
          />

          {/* Kart z-[110]: ekranın altından, backdrop'un önünde */}
          <div className="fixed z-[110] inset-x-4 bottom-[5.5rem] max-w-sm mx-auto
                          rounded-2xl px-5 py-4
                          bg-[rgba(8,12,26,0.93)] backdrop-blur-[28px]
                          border border-white/[0.13]
                          shadow-[0_8px_48px_rgba(0,0,0,0.7)]">
            <button
              onClick={() => setOpen(false)}
              aria-label="Kapat"
              className="absolute top-3.5 right-3.5 text-white/30 hover:text-white/65 transition-colors"
            >
              <X size={15} />
            </button>

            <p className="text-xs font-light text-white/78 leading-[1.7] pr-4">
              {MANIFESTO}
            </p>
            <p className="text-[11px] italic text-white/40 text-right mt-2.5">
              — Muhammet Vefa Yoksul
            </p>

            <div className="flex items-center gap-5 mt-3.5">
              {LINKS.map((l) => (
                <ActionLink key={l.label} {...l} />
              ))}
            </div>
          </div>
        </>,
        document.body
      )}

      {/* ── Masaüstü: sabit geniş panel ─────────────────────────────────────── */}
      <div className="hidden md:block fixed bottom-5 left-5 z-10 max-w-[300px]">
        <div className="rounded-xl px-4 py-3 bg-black/50 backdrop-blur-[16px] border border-white/10 shadow-[0_4px_24px_rgba(0,0,0,0.45)]">
          <p className="text-xs font-light text-white/80 leading-relaxed">
            {MANIFESTO}
          </p>
          <p className="text-xs italic text-white/50 text-right mt-2">
            — Muhammet Vefa Yoksul
          </p>
          <div className="flex items-center gap-4 mt-3">
            {LINKS.map((l) => (
              <ActionLink key={l.label} {...l} />
            ))}
          </div>
        </div>
      </div>
    </>
  );
}

function ActionLink({ href, icon, label }) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="group flex items-center gap-1.5 text-white/45 text-[11px] font-medium
                 transition-all duration-200 hover:-translate-y-0.5 hover:text-[#ff7a1a]"
    >
      <span className="transition-all duration-200
                       group-hover:drop-shadow-[0_0_7px_rgba(255,122,26,0.85)]">
        {icon}
      </span>
      <span>{label}</span>
    </a>
  );
}
