// Overview: the at-a-glance page. Every state, count and animation comes from the event stream or /api/health.
import { useMemo, useState } from "react";
import { AlertCard, deviceName } from "./alerts";
import { AlertEvent, classText, Device, monitorState, MonitorState, overview, State, TopologyNode, WindowEvent } from "./store";
import { ago, Card, clock, Empty, fmt, Icon, Metric, useIdsControl, useNow, useWidth } from "./ui";
import { Health } from "./useStream";

const HERO: Record<MonitorState, { title: string; sub: string; icon: string }> = {
  monitoring: { title: "Monitoring your IoT network", sub: "Edge Watch is analysing communication between your simulated smart devices. Nothing has been flagged in the last two minutes: no suspicious pattern was seen, which is not proof that the network is safe.", icon: "shield" },
  alert: { title: "Suspicious activity detected", sub: "", icon: "attack" },
  paused: { title: "Monitoring paused", sub: "Devices still talk to the message hub, but Edge Watch is not analysing their traffic until you resume.", icon: "pause" },
  stopped: { title: "Monitoring is not running", sub: "The detection service has not reported in the last 15 seconds. Earlier results below are kept for review. Start it again with the start script.", icon: "pause" },
  offline: { title: "Connection unavailable", sub: "This page cannot reach the Edge Watch service. It retries automatically; nothing shown below is live until it reconnects.", icon: "plug" },
  not_started: { title: "Monitoring has not started", sub: "Edge Watch has no event store yet. Start it with .\\scripts\\start-edgewatch.ps1, then this page updates by itself.", icon: "plug" },
};
const LIVE_STATES: Record<MonitorState, string> = { monitoring: "Active", alert: "Active", paused: "Paused", stopped: "Stopped", offline: "Offline", not_started: "Not started" };

// A replay has no 1 Hz topology events, so node state comes from its windows, judged by the replay's own clock.
export function nodesFromWindows(windows: WindowEvent[]): TopologyNode[] {
  const latest = new Map<string, WindowEvent>();
  for (const w of windows) latest.set(w.source_key, w);
  const end = windows.at(-1)?.window_end ?? 0;
  return [...latest.values()].map((w) => ({ source_key: w.source_key, msgs_per_s: (w.features.F12 + w.features.F09) / 5, state: w.state, score: w.score, predicted: w.prediction, silent: end - w.window_end > 15 }));
}
export const kindOf = (n?: TopologyNode) => (!n || n.silent ? "silent" : n.state ?? "normal");
/** One chart: hub messages per second, scheduled attack periods, suspicious checks and alerts, over the last five minutes. */
export function ActivityChart({ state, title = "Network activity", sub = "Messages per second through the hub, last 5 minutes" }: { state: State; title?: string; sub?: string }) {
  const [hover, setHover] = useState<number | null>(null);
  const [wrap, w] = useWidth(900);
  const span = 300, h = 200, left = 40, right = 8, top = 12, bottom = 34;
  const series = useMemo(() => {
    if (state.resources.length) return state.resources.map((r) => ({ t: r.ts, v: r.mqtt_msgs_per_s }));
    const seen = new Set<number>();
    return state.windows.filter((x) => !seen.has(x.window_end) && seen.add(x.window_end)).map((x) => ({ t: x.window_end, v: x.features.F25 / 5 })); // a replay has no 1 Hz monitor
  }, [state.resources, state.windows]);
  const end = series.at(-1)?.t ?? 0, start = end - span;
  const visible = series.filter((p) => p.t >= start);
  const max = Math.max(1, ...visible.map((p) => p.v)) * 1.15;
  const X = (t: number) => left + ((t - start) / span) * (w - left - right), Y = (v: number) => top + (1 - v / max) * (h - top - bottom);
  const pts = visible.map((p) => `${X(p.t).toFixed(1)},${Y(p.v).toFixed(1)}`);
  const bands = state.markers.filter((m) => m.marker === "scheduled_attack" && m.start_ns! / 1e9 < end && m.end_ns! / 1e9 > start);
  const flagged = useMemo(() => [...new Set(state.windows.filter((x) => x.state !== "normal" && x.window_start >= start).map((x) => x.window_start))], [state.windows, start]);
  const marks = state.alerts.filter((a) => a.start_ns / 1e9 > start);
  const point = hover == null || !visible.length ? null : visible.reduce((best, p) => (Math.abs(p.t - hover) < Math.abs(best.t - hover) ? p : best), visible[0]);
  return (
    <Card title={title} sub={sub} className="activity-card"
      actions={<div className="legend-row"><span className="lg lg-line">Messages/s</span><span className="lg lg-band">Simulated attack</span><span className="lg lg-suspicious">Suspicious check</span><span className="lg lg-alert">Alert</span></div>}>
      {!visible.length ? <Empty icon="wave" title="No traffic yet">The chart starts as soon as devices send messages.</Empty> : (
        <div className="chart-wrap" ref={wrap} onMouseLeave={() => setHover(null)} onMouseMove={(e) => { const b = e.currentTarget.getBoundingClientRect(); setHover(start + (((e.clientX - b.left) / b.width) * w - left) / (w - left - right) * span); }}>
          <svg viewBox={`0 0 ${w} ${h}`} className="chart" preserveAspectRatio="none" role="img" aria-label="Messages per second through the hub, last five minutes, with attack periods and alerts">
            <defs><linearGradient id="area" x1="0" x2="0" y1="0" y2="1"><stop offset="0%" stopColor="var(--accent)" stopOpacity=".35" /><stop offset="100%" stopColor="var(--accent)" stopOpacity="0" /></linearGradient></defs>
            {bands.map((b, i) => { const x0 = Math.max(left, X(b.start_ns! / 1e9)); return <rect key={i} x={x0} y={top} width={Math.max(1, X(Math.min(end, b.end_ns! / 1e9)) - x0)} height={h - top - bottom} className="band" />; })}
            {[0, 0.5, 1].map((f) => <g key={f}><line x1={left} x2={w - right} y1={Y(max * f)} y2={Y(max * f)} className="grid-line" /><text x={left - 6} y={Y(max * f) + 3} textAnchor="end" className="axis">{fmt(max * f, max < 10 ? 1 : 0)}</text></g>)}
            {(w < 560 ? [0, 120, 240, 300] : [0, 60, 120, 180, 240, 300]).map((s) => <text key={s} x={X(start + s)} y={h - 4} textAnchor={s === 0 ? "start" : s === 300 ? "end" : "middle"} className="axis">{s === 300 ? "now" : `−${(300 - s) / 60} min`}</text>)}
            {flagged.map((t) => <rect key={t} x={X(t)} y={h - bottom + 4} width={Math.max(2, X(t + 5) - X(t))} height={7} className="flag-strip" />)}
            {pts.length > 1 && <polygon points={`${X(visible[0].t)},${h - bottom} ${pts.join(" ")} ${X(visible.at(-1)!.t)},${h - bottom}`} fill="url(#area)" />}
            <polyline points={pts.join(" ")} className="line line-a" vectorEffect="non-scaling-stroke" />
            {marks.map((a) => <path key={a.alert_id} transform={`translate(${X(a.start_ns / 1e9)} ${top + 7})`} d="M0 -6 L6 0 L0 6 L-6 0Z" className={`alert-mark sev-${a.severity}`} />)}
            {point && <line x1={X(point.t)} x2={X(point.t)} y1={top} y2={h - bottom} className="crosshair" />}
          </svg>
          {point && <div className="tooltip" style={{ left: `${Math.min(78, (X(point.t) / w) * 100)}%`, top: 8 }}><span>{clock(point.t)}</span><b>{fmt(point.v)} messages/s</b></div>}
        </div>
      )}
    </Card>
  );
}

/** Headline status and the four indicators, from backend facts only. Compact: one line of status above the metrics. */
export function StatusSummary({ state, health, connected, devices, onOpen, go }: { state: State; health: Health | null; connected: boolean; devices: Map<string, Device>; onOpen: (a: AlertEvent) => void; go: (route: string) => void }) {
  const now = useNow(2000);
  const ms = monitorState(health, connected, state, now);
  const o = overview(state);
  const { toggle, error } = useIdsControl(health?.ids_enabled !== false);
  const latest = useMemo(() => [...state.alerts].sort((a, b) => b.start_ns - a.start_ns)[0], [state.alerts]);
  const hero = HERO[ms];
  return (
    <>
      <section className={`hero hero-compact hero-${ms}`} aria-live="polite">
        <div className="hero-orb"><span className="orb-ring" /><Icon name={hero.icon} size={26} /></div>
        <div className="hero-text">
          <p className="eyebrow">{state.provenances[0] === "replay" ? "Replay of recorded lab traffic" : "Simulated smart home"} · {LIVE_STATES[ms]}</p>
          <h1>{hero.title}</h1>
          <p className="hero-sub">{ms === "alert" && latest ? <>{deviceName(devices, latest.source_key)}: <b>{classText(latest.predicted_class).title.toLowerCase()}</b>, {ago(latest.last_window_ns / 1e9, now)}. Edge Watch raised an alert; it watches traffic and does not stop it.</> : hero.sub}</p>
        </div>
        <div className="hero-actions">
          {ms === "alert" && latest && <button className="btn btn-primary" onClick={() => onOpen(latest)}>See what happened <Icon name="arrow" size={16} /></button>}
          {ms === "paused" && <button className="btn btn-primary" onClick={toggle}>Resume monitoring</button>}
          <button className="btn" onClick={() => go("attack")}><Icon name="play" size={16} /> Attack Simulator</button>
          {error && <span className="warn" role="status">{error}</span>}
        </div>
      </section>
      <div className="metrics">
        <Metric metric="monitoring" icon="shield" label="Monitoring" value={LIVE_STATES[ms]} tone={ms === "monitoring" || ms === "alert" ? "ok" : "warn"} sub={ms === "monitoring" || ms === "alert" ? `Checks every device every ${state.run?.window_s ?? 5} seconds` : "Not analysing traffic now"} hint="From the detection service's own heartbeat" />
        <Metric metric="sources" icon="router" label="Devices" value={String(o.activeSources)} unit="sending now" sub={`${o.observedSources} seen this session`} hint="Distinct traffic sources Edge Watch observed" />
        <Metric metric="alerts" icon="bell" label="Alerts" value={String(o.alerts)} tone={ms === "alert" ? "bad" : o.alerts ? "warn" : "ok"} sub={o.alerts ? `${o.severity.high} high · ${o.severity.medium} medium · ${o.severity.low} low` : "None this session"} hint="Alerts raised in this monitoring session" />
        <Metric metric="activity" icon="wave" label="Network activity" value={fmt(o.msgsPerS)} unit="messages/s" sub="Through the smart-home hub" hint="Measured once per second from the hub's traffic" />
      </div>
    </>
  );
}

export function RecentIncidents({ state, devices, onOpen, go }: { state: State; devices: Map<string, Device>; onOpen: (a: AlertEvent) => void; go: (route: string) => void }) {
  const recent = useMemo(() => [...state.alerts].sort((a, b) => b.start_ns - a.start_ns), [state.alerts]);
  return (
    <Card title="Recent incidents" sub="The latest suspicious events, newest first" className="incidents-card" actions={recent.length > 0 ? <button className="btn btn-ghost" onClick={() => go("alerts")}>View all <Icon name="arrow" size={16} /></button> : undefined}>
      <div className="alert-queue">
        {recent.slice(0, 5).map((a) => <AlertCard key={a.alert_id} alert={a} devices={devices} onOpen={onOpen} />)}
        {!recent.length && (state.windows.length ? <p className="clear"><Icon name="check" size={18} />No alerts in this monitoring session</p> : <Empty icon="clock" title="Nothing to assess yet">Incidents appear here as soon as Edge Watch flags one.</Empty>)}
      </div>
    </Card>
  );
}
