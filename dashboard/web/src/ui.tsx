// Design-system primitives shared by every view. Icons are inline SVG paths on a 24-unit grid, so no icon dependency is needed.
import { ReactNode, useEffect, useState } from "react";

const PATHS: Record<string, string> = {
  thermo: "M14 14.76V3.5a2.5 2.5 0 0 0-5 0v11.26a4.5 4.5 0 1 0 5 0z",
  motion: "M12 10a2 2 0 1 0 0 4a2 2 0 1 0 0-4z M16.24 7.76a6 6 0 0 1 0 8.49 M7.76 16.24a6 6 0 0 1 0-8.49 M19.07 4.93a10 10 0 0 1 0 14.14 M4.93 19.07a10 10 0 0 1 0-14.14",
  bulb: "M9 18h6 M10 22h4 M12 2a7 7 0 0 0-4 12.7V17h8v-2.3A7 7 0 0 0 12 2z",
  switch: "M7 7h10a5 5 0 0 1 0 10H7A5 5 0 0 1 7 7z M16 9a3 3 0 1 0 0 6a3 3 0 1 0 0-6z",
  door: "M5 21V4a1 1 0 0 1 1-1h12a1 1 0 0 1 1 1v17 M3 21h18 M15 12h.01",
  moon: "M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z",
  chip: "M6 6h12v12H6z M9.5 9.5h5v5h-5z M9 2v4 M15 2v4 M9 18v4 M15 18v4 M2 9h4 M2 15h4 M18 9h4 M18 15h4",
  wave: "M22 12h-4l-3 9L9 3l-3 9H2",
  refresh: "M21 12a9 9 0 1 1-2.64-6.36L21 8 M21 3v5h-5",
  attack: "M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z M12 9v4 M12 17h.01",
  unknown: "M12 2a10 10 0 1 0 0 20a10 10 0 1 0 0-20z M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3 M12 17h.01",
  hub: "M3 4h18v6H3z M3 14h18v6H3z M7 7h.01 M7 17h.01",
  shield: "M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z",
  check: "M20 6 9 17l-5-5",
  home: "M3 10.5 12 3l9 7.5V21H3z M9 21v-6h6v6",
  play: "M6 4l14 8-14 8z",
  stop: "M6 6h12v12H6z",
  bell: "M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9 M13.73 21a2 2 0 0 1-3.46 0",
  sliders: "M4 21v-7 M4 10V3 M12 21v-9 M12 8V3 M20 21v-5 M20 12V3 M1 14h6 M9 8h6 M17 16h6",
  clock: "M12 2a10 10 0 1 0 0 20a10 10 0 1 0 0-20z M12 6v6l4 2",
  x: "M18 6 6 18 M6 6l12 12",
  pause: "M6 4h4v16H6z M14 4h4v16h-4z",
  router: "M2 14h20v6H2z M6 17h.01 M10 17h.01 M12 14V9 M8.5 6.5a5 5 0 0 1 7 0 M5.5 3.5a9 9 0 0 1 13 0",
  arrow: "M5 12h14 M12 5l7 7-7 7",
  info: "M12 2a10 10 0 1 0 0 20a10 10 0 1 0 0-20z M12 16v-4 M12 8h.01",
  flask: "M9 3h6 M10 3v6L4 20a1 1 0 0 0 .9 1.5h14.2A1 1 0 0 0 20 20L14 9V3",
  plug: "M9 2v6 M15 2v6 M6 8h12v4a6 6 0 0 1-12 0z M12 18v4",
  lock: "M5 11h14v10H5z M8 11V7a4 4 0 0 1 8 0v4 M12 15v2",
  camera: "M3 7h4l2-3h6l2 3h4v13H3z M12 9.5a3.5 3.5 0 1 0 0 7a3.5 3.5 0 1 0 0-7z",
  dial: "M12 3a9 9 0 1 0 0 18a9 9 0 1 0 0-18z M12 12l3.5-3.5 M8 16.5h8",
  smoke: "M12 3a9 9 0 1 0 0 18a9 9 0 1 0 0-18z M12 9a3 3 0 1 0 0 6a3 3 0 1 0 0-6z M12 3v2 M12 19v2",
  plus: "M12 5v14 M5 12h14",
  doorOpen: "M5 21V4a1 1 0 0 1 1-1h8 M3 21h18 M14 3l5 2v16l-5-1z M16.5 12h.01",
  unlock: "M5 11h14v10H5z M8 11V7a4 4 0 0 1 7.5-2 M12 15v2",
  flame: "M12 22c4 0 7-3 7-7 0-4-3-6-4-9-1 3-3 4-3 4s-1-3 0-6c-4 2-7 6-7 11 0 4 3 7 7 7z",
  trash: "M4 7h16 M9 7V4h6v3 M6 7l1 13h10l1-13",
  move: "M12 3v18 M3 12h18 M12 3l-3 3 M12 3l3 3 M12 21l-3-3 M12 21l3-3 M3 12l3-3 M3 12l3 3 M21 12l-3-3 M21 12l-3 3",
};

export function Icon({ name, size = 20, className = "" }: { name: string; size?: number; className?: string }) {
  return <svg width={size} height={size} viewBox="0 0 24 24" className={`icon ${className}`} aria-hidden="true" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round"><path d={PATHS[name] ?? PATHS.unknown} /></svg>;
}
/** The same icon placed inside an SVG scene, centred on the current origin. */
export function SvgIcon({ name, size = 20 }: { name: string; size?: number }) {
  return <g transform={`translate(${-size / 2} ${-size / 2}) scale(${size / 24})`} fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round"><path d={PATHS[name] ?? PATHS.unknown} /></g>;
}

export type Tone = "ok" | "warn" | "bad" | "info" | "muted";
export const SEV_TONE: Record<string, Tone> = { high: "bad", medium: "warn", low: "info" };
export const Pill = ({ tone = "muted", children, title }: { tone?: Tone; children: ReactNode; title?: string }) => <span className={`pill pill-${tone}`} title={title}>{children}</span>;

export function Metric({ icon, label, value, unit, sub, tone = "info", metric, hint }: { icon: string; label: string; value: string; unit?: string; sub?: ReactNode; tone?: Tone; metric: string; hint?: string }) {
  return (
    <div className={`metric metric-${tone}`} data-metric={metric} title={hint}>
      <span className="metric-icon"><Icon name={icon} /></span>
      <span className="metric-label">{label}</span>
      <span className="metric-value"><b>{value}</b>{unit && <small>{unit}</small>}</span>
      {sub && <span className="metric-sub">{sub}</span>}
    </div>
  );
}

export function PageHead({ eyebrow, title, sub, actions }: { eyebrow?: string; title: string; sub?: ReactNode; actions?: ReactNode }) {
  return (
    <header className="page-head">
      <div>{eyebrow && <p className="eyebrow">{eyebrow}</p>}<h1>{title}</h1>{sub && <p className="page-sub">{sub}</p>}</div>
      {actions && <div className="page-actions">{actions}</div>}
    </header>
  );
}

export function Card({ title, sub, actions, children, className = "" }: { title?: string; sub?: ReactNode; actions?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={`card ${className}`}>
      {(title || actions) && <header className="card-head"><div>{title && <h2>{title}</h2>}{sub && <p className="card-sub">{sub}</p>}</div>{actions}</header>}
      {children}
    </section>
  );
}

export const Empty = ({ icon = "info", title, children }: { icon?: string; title: string; children?: ReactNode }) => (
  <div className="empty-state"><Icon name={icon} size={28} /><b>{title}</b>{children && <p>{children}</p>}</div>
);

export function useNow(ms = 1000) {
  const [now, setNow] = useState(Date.now() / 1000);
  useEffect(() => { const t = setInterval(() => setNow(Date.now() / 1000), ms); return () => clearInterval(t); }, [ms]);
  return now;
}

/** Rendered width of an element, so SVG charts can draw at 1:1 instead of stretching their text. */
export function useWidth(fallback: number) {
  const [el, setEl] = useState<HTMLElement | null>(null);
  const [w, setW] = useState(fallback);
  useEffect(() => { if (!el) return; const o = new ResizeObserver(([e]) => setW(Math.max(240, Math.round(e.contentRect.width)))); o.observe(el); return () => o.disconnect(); }, [el]);
  return [setEl, w] as const;
}

export const fmt =(v: number | null | undefined, d = 1) => (v == null || Number.isNaN(v) ? "—" : v >= 1000 ? Math.round(v).toLocaleString() : v.toFixed(d));
export const clock = (ts: number) => new Date(ts * 1000).toLocaleTimeString([], { hour12: false });
export function ago(ts: number, now: number) {
  const s = Math.max(0, now - ts);
  return s < 10 ? "just now" : s < 60 ? `${Math.round(s)} s ago` : s < 3600 ? `${Math.round(s / 60)} min ago` : s < 86400 ? `${Math.round(s / 3600)} h ago` : new Date(ts * 1000).toLocaleDateString();
}
export const duration = (s: number) => (s < 60 ? `${Math.round(s)} s` : `${Math.floor(s / 60)} min ${Math.round(s % 60)} s`);

/** POST with the optional control token. Only control endpoints need it. */
export async function send(url: string, body?: object): Promise<{ ok: boolean; status: number; data: any }> {
  const post = (token?: string) => fetch(url, { method: "POST", headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) }, body: JSON.stringify(body ?? {}) });
  try {
    let r = await post();
    if (r.status === 401) r = await post(window.prompt("Control token") ?? undefined);
    const data = await r.json().catch(() => null);
    return { ok: r.ok, status: r.status, data };
  } catch {
    return { ok: false, status: 0, data: { detail: "API unreachable" } };
  }
}
export const detail = (d: any) => (typeof d?.detail === "string" ? d.detail : Array.isArray(d?.detail) ? d.detail.map((x: any) => `${x.loc?.at(-1)}: ${x.msg}`).join("; ") : "request refused");

/** Pause or resume IDS capture. The broker and traffic are never touched. */
export function useIdsControl(enabled: boolean) {
  const [error, setError] = useState<string | null>(null);
  const toggle = async () => {
    const r = await send("/api/control", { action: enabled ? "disable" : "enable" });
    setError(r.ok ? null : `Control refused (${r.status}): ${detail(r.data)}`);
  };
  return { toggle, error };
}
