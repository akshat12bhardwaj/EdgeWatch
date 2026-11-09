// Alerts: plain-language cards, the incident drawer, and the persisted alert history. Technical evidence stays one click away.
import { useEffect, useMemo, useRef, useState } from "react";
import { AlertEvent, classText, Device, FEATURE_NAMES, FEATURE_PLAIN, State, STATUS_PLAIN, WindowEvent } from "./store";
import { ago, Card, clock, duration, Empty, fmt, Icon, PageHead, Pill, SEV_TONE, useNow } from "./ui";
import { json } from "./useStream";

export const deviceName = (devices: Map<string, Device>, key: string) => devices.get(key)?.name ?? `Device ${key.slice(-4)}`;
const STATUS_TONE = { matches_scheduled_attack: "ok", no_scheduled_attack: "warn", unverified_prediction: "muted" } as const;
const COUNTS = new Set(["F01", "F02", "F03", "F04", "F05", "F06", "F09", "F10", "F12", "F13", "F14", "F15", "F19", "F23", "F24", "F25"]); // per-window counts; the rest are means, ratios or maxima
const KIND_ICON: Record<string, string> = { flood: "wave", bruteforce: "plug", malformed: "attack", lowrate: "clock", wildcard_subscribe: "motion" };

export function AlertCard({ alert, devices, onOpen, selected, full = false }: { alert: AlertEvent; devices: Map<string, Device>; onOpen: (a: AlertEvent) => void; selected?: boolean; full?: boolean }) {
  const now = useNow(10000), t = classText(alert.predicted_class);
  return (
    <button className={`alert-row sev-${alert.severity} ${selected ? "selected" : ""}`} onClick={() => onOpen(alert)} data-alert={alert.alert_id}>
      <span className="ac-icon"><Icon name={KIND_ICON[alert.predicted_class] ?? "attack"} /></span>
      <span className="ac-main">
        <b>{t.title}</b>
        <span className="ac-meta">{deviceName(devices, alert.source_key)} · <time title={new Date(alert.start_ns / 1e6).toLocaleString()}>{ago(alert.start_ns / 1e9, now)}</time></span>
        {full && <span className="ac-what">{t.what}</span>}
      </span>
      <span className="ac-side">
        <Pill tone={SEV_TONE[alert.severity]}>{alert.severity} severity</Pill>
        <Pill tone={STATUS_TONE[alert.status]}>{STATUS_PLAIN[alert.status]}</Pill>
      </span>
    </button>
  );
}

function Spark({ values, label }: { values: number[]; label: string }) {
  const max = Math.max(1e-9, ...values), n = Math.max(1, values.length - 1);
  return <svg viewBox="0 0 100 24" className="spark" preserveAspectRatio="none" role="img" aria-label={`${label}, last ${values.length} windows`}><polyline points={values.map((v, i) => `${(i / n) * 100},${22 - (v / max) * 20}`).join(" ")} vectorEffect="non-scaling-stroke" /></svg>;
}

export function IncidentDrawer({ alert, state, devices, onClose }: { alert: AlertEvent; state: State; devices: Map<string, Device>; onClose: () => void }) {
  const [detail, setDetail] = useState<{ history?: WindowEvent[] } | null>(null);
  const [error, setError] = useState(false);
  const close = useRef<HTMLButtonElement>(null);
  useEffect(() => { close.current?.focus(); }, [alert.alert_id]);
  useEffect(() => { setDetail(null); setError(false); json<any>(`/api/alerts/${alert.alert_id}`).then((d) => (d ? setDetail(d) : setError(true))); }, [alert.alert_id, alert.window_ids?.length]);
  const history = detail?.history ?? state.windows.filter((w) => w.source_key === alert.source_key).slice(-12);
  const last = history.at(-1)?.features;
  const schedule = state.markers.find((m) => m.marker === "scheduled_attack" && m.source_key === alert.source_key && m.start_ns! < alert.last_window_ns + 5e9 && m.end_ns! > alert.start_ns);
  const ttd = schedule ? (alert.start_ns + 2 * 5e9 - schedule.start_ns!) / 1e9 : null; // same definition as episodeOutcomes: end of the k-th window
  const t = classText(alert.predicted_class), device = devices.get(alert.source_key);
  const top = (alert.evidence ?? []).slice(0, 3);
  return (
    <>
      <div className="scrim" onClick={onClose} />
      <aside className="drawer" role="dialog" aria-modal="true" aria-label={`Incident: ${t.title}`}>
        <header className="drawer-head">
          <div>
            <p className="eyebrow">Incident · {clock(alert.start_ns / 1e9)}</p>
            <h2>{t.title}</h2>
            <div className="pill-row"><Pill tone={SEV_TONE[alert.severity]}>{alert.severity} severity</Pill><Pill tone={STATUS_TONE[alert.status]}>{STATUS_PLAIN[alert.status]}</Pill></div>
          </div>
          <button ref={close} className="icon-btn" onClick={onClose} aria-label="Close incident (Esc)"><Icon name="x" /></button>
        </header>
        <dl className="facts">
          <div><dt>Device</dt><dd>{deviceName(devices, alert.source_key)}</dd></div>
          <div><dt>Started</dt><dd>{new Date(alert.start_ns / 1e6).toLocaleTimeString([], { hour12: false })}</dd></div>
          <div><dt>Lasted</dt><dd>{duration(alert.duration_s)}</dd></div>
          {ttd != null && <div><dt>Time to alert</dt><dd>{fmt(ttd)} s after the simulated attack began</dd></div>}
        </dl>
        <section className="explain">
          <h3>What happened?</h3>
          <p>{t.what}</p>
          {device?.kind === "attacker" && <p className="dim">This source is the demo's simulated attacker, according to the lab's schedule.</p>}
          {device?.kind === "profile" && <p className="dim">Its simulated profile is “{device.name.replace(/ \d+$/, "")}”, as reported by the lab runner.</p>}
          <h3>Why was it flagged?</h3>
          {top.length ? (
            <>
              <p>The detector checks each 5-second slice of this device's traffic. These measurements weighed most in its decision, shown against typical values for normal devices:</p>
              <ul className="evidence-plain">{top.map((e) => {
                const ratio = e.baseline_p50 ? e.value / e.baseline_p50 : null;
                return <li key={e.feature}><b>{FEATURE_PLAIN[e.feature] ?? e.feature}</b><span>{fmt(e.value, 1)}{COUNTS.has(e.feature) && " in 5 s"}{e.baseline_p50 != null && <> · normal devices: {fmt(e.baseline_p50, 1)}</>}{ratio != null && ratio > 1.5 && <> · about {fmt(ratio, 0)}× normal</>}</span></li>;
              })}</ul>
            </>
          ) : <p>A detection rule matched this traffic. The rule's measurements are in the technical details.</p>}
          <p className="dim">An alert is raised only when consecutive slices look suspicious, which filters out one-off blips.</p>
          <h3>What could it mean?</h3>
          <p>{t.risk}</p>
          <h3>What did Edge Watch do?</h3>
          <p>Detected suspicious activity and raised this alert. Edge Watch watches a passive copy of the traffic; it does not stop or change any messages.</p>
        </section>
        <details className="tech">
          <summary>Technical details</summary>
          <dl className="facts">
            <div><dt>Source pseudonym</dt><dd className="num">{alert.source_key}</dd></div>
            <div><dt>Predicted class</dt><dd className="num">{alert.predicted_class}</dd></div>
            <div><dt>Detector</dt><dd className="num">{alert.kind === "rule" ? "rule indicator" : alert.model_id ?? "—"}</dd></div>
            <div><dt>Score</dt><dd className="num">{alert.score == null ? "rule" : fmt(alert.score, 3)}</dd></div>
            <div><dt>Windows</dt><dd className="num">{alert.window_ids?.length ?? 0}</dd></div>
            <div><dt>Alert ID</dt><dd className="num">{alert.alert_id.slice(0, 12)}</dd></div>
          </dl>
          {error && <p className="warn">Window history could not be loaded.</p>}
          <div className="scroll-x">
            <table className="evidence">
              <thead><tr><th>Feature</th><th className="r">Value</th><th className="r">Benign median</th><th className="r">Contribution</th><th>Last {history.length} windows</th></tr></thead>
              <tbody>
                {(alert.evidence ?? []).map((e) => (
                  <tr key={e.feature}><td><b className="num">{e.feature}</b> <span className="dim">{FEATURE_NAMES[e.feature]}</span></td><td className="r num">{fmt(e.value, 2)}</td><td className="r num">{fmt(e.baseline_p50, 2)}</td><td className="r num">{e.contribution == null ? "—" : e.contribution.toFixed(3)}</td><td><Spark label={e.feature} values={history.map((w) => w.features?.[e.feature] ?? 0)} /></td></tr>
                ))}
              </tbody>
            </table>
          </div>
          {last && <><h3>Raw counts, latest window</h3><div className="counts">{["F09", "F10", "F12", "F13", "F03", "F04", "F23", "F22"].map((f) => <div key={f}><b className="num">{fmt(last[f], 0)}</b><span>{FEATURE_NAMES[f]}</span></div>)}</div></>}
        </details>
        <footer className="drawer-foot">Evidence shows what the model weighted; it is not proof of malicious intent.</footer>
      </aside>
    </>
  );
}

type Run = { run_id: string; provenance: string | null; started: number; windows: number; alerts: number | null; scenario: string | null; model_id: string | null };
const SCENARIO_LABEL: Record<string, string> = { "demo-benign-then-attacks": "Startup demo", "dashboard-controlled": "Security demos", "benign-base": "Normal traffic only" };
const runLabel = (r: Run) => `${new Date(r.started * 1000).toLocaleString([], { dateStyle: "medium", timeStyle: "short" })} · ${SCENARIO_LABEL[r.scenario ?? ""] ?? r.scenario ?? "session"}${r.provenance === "replay" ? " (replay)" : ""}`;

export function AlertsPage({ state, devices, onOpen, source }: { state: State; devices: Map<string, Device>; onOpen: (a: AlertEvent) => void; source?: string }) {
  const [runs, setRuns] = useState<Run[]>([]);
  const [filters, setFilters] = useState({ run_id: state.runId ?? "", severity: "", kind: "", status: "", predicted_class: "", source: source ?? "" });
  const [alerts, setAlerts] = useState<AlertEvent[] | null | undefined>(undefined);
  useEffect(() => { json<Run[]>("/api/runs").then((r) => setRuns(r ?? [])); }, []);
  useEffect(() => { if (source !== undefined) setFilters((f) => ({ ...f, source })); }, [source]);
  useEffect(() => {
    const q = new URLSearchParams({ limit: "500", ...Object.fromEntries(Object.entries(filters).filter(([, v]) => v)) });
    json<AlertEvent[]>(`/api/alerts?${q}`).then((a) => setAlerts(a));
  }, [filters, state.alerts.length]);
  const set = (k: string, v: string) => setFilters((f) => ({ ...f, [k]: v }));
  const classes = useMemo(() => [...new Set((alerts ?? []).map((a) => a.predicted_class))], [alerts]);
  const counts = { high: 0, medium: 0, low: 0 };
  for (const a of alerts ?? []) counts[a.severity]++;
  return (
    <div className="page">
      <PageHead eyebrow="Security events" title="Alerts" sub="Every suspicious event Edge Watch has raised, explained in plain language. Select one to see what happened." />
      <Card className="filters-card">
        <div className="filters">
          <div className="seg" role="group" aria-label="Severity">
            {["", "high", "medium", "low"].map((s) => <button key={s} className={filters.severity === s ? "on" : ""} aria-pressed={filters.severity === s} onClick={() => set("severity", s)}>{s ? `${s[0].toUpperCase()}${s.slice(1)}` : "All"}</button>)}
          </div>
          <label>Monitoring session<select value={filters.run_id} onChange={(e) => set("run_id", e.target.value)}><option value="">All sessions</option>{runs.map((r) => <option key={r.run_id} value={r.run_id}>{runLabel(r)} · {r.alerts ?? 0} alerts</option>)}</select></label>
          <label>Device<select value={filters.source} onChange={(e) => set("source", e.target.value)}><option value="">Any device</option>{[...devices.values()].map((d) => <option key={d.key} value={d.key}>{d.name}</option>)}{filters.source && !devices.has(filters.source) && <option value={filters.source}>{deviceName(devices, filters.source)}</option>}</select></label>
        </div>
        <details className="more">
          <summary>More filters</summary>
          <div className="filters">
            <label>Alert type<select value={filters.predicted_class} onChange={(e) => set("predicted_class", e.target.value)}><option value="">Any</option>{classes.map((c) => <option key={c} value={c}>{classText(c).title}</option>)}</select></label>
            <label>Detected by<select value={filters.kind} onChange={(e) => set("kind", e.target.value)}><option value="">Any</option><option value="model">AI model</option><option value="rule">Simple rule</option></select></label>
            <label>Demo schedule<select value={filters.status} onChange={(e) => set("status", e.target.value)}><option value="">Any</option>{Object.entries(STATUS_PLAIN).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></label>
          </div>
        </details>
      </Card>
      {alerts === undefined ? <p className="loading-line">Loading alerts…</p> : alerts === null ? <p className="warn">Alerts could not be loaded from the Edge Watch service.</p> : !alerts.length ? (
        <Empty icon="check" title="No alerts match these filters">Edge Watch has not raised an alert that fits this selection.</Empty>
      ) : (
        <>
          <p className="list-summary">{alerts.length} alerts · {counts.high} high · {counts.medium} medium · {counts.low} low</p>
          <div className="alert-list">{alerts.map((a) => <AlertCard key={a.alert_id} alert={a} devices={devices} onOpen={onOpen} full />)}</div>
        </>
      )}
      <p className="note dim">An alert means a device's traffic looked unlike normal device traffic for at least two consecutive 5-second checks. “Matches a simulated attack” is checked against the demo's own schedule, recorded separately from the detector.</p>
    </div>
  );
}
