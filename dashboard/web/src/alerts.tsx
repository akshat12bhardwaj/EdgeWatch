// Alerts: plain-language cards, the incident drawer, and the persisted alert history. Technical evidence stays one click away.
import { useEffect, useRef, useState } from "react";
import { AlertEvent, classText, Device, FEATURE_NAMES, FEATURE_PLAIN, State, STATUS_PLAIN, WindowEvent } from "./store";
import { ago, Card, clock, detail as requestDetail, duration, Empty, fmt, Icon, PageHead, Pill, send, SEV_TONE, useNow } from "./ui";
import { ALERT_HISTORY_CLEARED, json } from "./useStream";

export const deviceName = (devices: Map<string, Device>, key: string) => devices.get(key)?.name ?? `Unidentified source ${key.slice(-4)}`;
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
        <footer className="drawer-foot"><a href="#/home" onClick={onClose}>View home network</a><br />Evidence shows what the model weighted; it is not proof of malicious intent.</footer>
      </aside>
    </>
  );
}

export const alertHistoryRequest = (accepted: boolean) => accepted ? { scope: "all", run_id: null, confirmation: "CLEAR ALERT HISTORY" } : null;

function ClearHistory({ onCleared }: { onCleared: (ids: string[]) => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [accepted, setAccepted] = useState(false), [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const request = alertHistoryRequest(accepted);
  async function clear() {
    if (!request || busy) return;
    setBusy(true); setError(null);
    const result = await send("/api/alerts/history/clear", request);
    const data = result.data;
    if (!result.ok) setError(`History was not cleared (${result.status}): ${requestDetail(data)}`);
    else if (!Array.isArray(data?.deleted_alert_ids) || !data.deleted_alert_ids.every((id: unknown) => typeof id === "string") || typeof data?.remaining_alerts !== "number") setError("The service returned an unexpected response. Reload the history to check its current state.");
    else {
      window.dispatchEvent(new CustomEvent(ALERT_HISTORY_CLEARED, { detail: data.deleted_alert_ids }));
      onCleared(data.deleted_alert_ids);
      dialog.current?.close();
    }
    setBusy(false);
  }
  return <>
    <button className="btn btn-danger btn-sm" onClick={() => { setAccepted(false); setError(null); dialog.current?.showModal(); }}>Clear Alert History</button>
    <dialog ref={dialog} className="card confirm-dialog" aria-labelledby="clear-history-title" aria-describedby="clear-history-description" onCancel={(e) => { if (busy) e.preventDefault(); }}>
      <h2 id="clear-history-title">Clear Alert History?</h2>
      <p id="clear-history-description">This permanently deletes every stored security alert, from all monitoring sessions including the current one. Monitoring keeps running and new alerts appear as usual. Devices, layouts, models, datasets and other telemetry are not changed.</p>
      <label className="check"><input type="checkbox" checked={accepted} disabled={busy} onChange={(e) => setAccepted(e.target.checked)} />I understand that deleted alerts cannot be restored.</label>
      {error && <p role="alert" className="warn">{error}</p>}
      <div className="row-actions"><button className="btn btn-sm" disabled={busy} onClick={() => dialog.current?.close()}>Cancel</button><button className="btn btn-danger btn-sm" disabled={!request || busy} onClick={clear}>{busy ? "Clearing…" : "Clear Alert History"}</button></div>
    </dialog>
  </>;
}

/** The alerts a finished simulation produced, by verified alert ID; unknown IDs are dropped rather than guessed. */
export function focusedAlerts(focus: string, fetched: AlertEvent[] | null | undefined, live: AlertEvent[]) {
  return focus.split(",").filter(Boolean).map((id) => fetched?.find((a) => a.alert_id === id) ?? live.find((a) => a.alert_id === id)).filter((a): a is AlertEvent => !!a);
}

export function AlertsPage({ state, devices, onOpen, source, focus }: { state: State; devices: Map<string, Device>; onOpen: (a: AlertEvent) => void; source?: string; focus?: string }) {
  const [filters, setFilters] = useState({ time: "all", from: "", to: "", severity: "", source: source ?? "" });
  const [alerts, setAlerts] = useState<AlertEvent[] | null | undefined>(undefined);
  const [revision, setRevision] = useState(0), [notice, setNotice] = useState<string | null>(null);
  const historyRevision = useRef(0);
  useEffect(() => { if (source !== undefined) setFilters((f) => ({ ...f, source })); }, [source]);
  useEffect(() => {
    let active = true;
    const requestRevision = historyRevision.current;
    const qFilters: Record<string, string> = { limit: "500" };
    if (filters.severity) qFilters.severity = filters.severity;
    if (filters.source) qFilters.source = filters.source;
    const now = new Date();
    if (filters.time === "hour") qFilters.since = String(Date.now() / 1000 - 3600);
    if (filters.time === "today") { const start = new Date(now); start.setHours(0, 0, 0, 0); qFilters.since = String(start.getTime() / 1000); }
    if (filters.time === "week") qFilters.since = String(Date.now() / 1000 - 7 * 86400);
    if (filters.time === "custom" && filters.from) qFilters.since = String(new Date(`${filters.from}T00:00:00`).getTime() / 1000);
    if (filters.time === "custom" && filters.to) qFilters.until = String(new Date(`${filters.to}T23:59:59.999`).getTime() / 1000);
    const q = new URLSearchParams(qFilters);
    json<AlertEvent[]>(`/api/alerts?${q}`).then((a) => { if (active && requestRevision === historyRevision.current) setAlerts(a); });
    return () => { active = false; };
  }, [filters, state.alerts.length, revision]);
  const set = (k: string, v: string) => setFilters((f) => ({ ...f, [k]: v }));
  const selectableDevices = [...devices.values()].filter((d) => d.kind !== "unknown");
  const focused = focus === undefined ? null : focusedAlerts(focus, alerts, state.alerts);
  const opened = useRef<string | null>(null);
  useEffect(() => { // open the simulation's single alert once; several are listed instead
    if (focused?.length === 1 && opened.current !== focus) { opened.current = focus!; onOpen(focused[0]); }
  }, [focus, focused?.length]);
  const counts = { high: 0, medium: 0, low: 0 };
  for (const a of alerts ?? []) counts[a.severity]++;
  return (
    <div className="page">
      <PageHead eyebrow="Security events" title="Alerts" sub="Every suspicious event Edge Watch has raised, explained in plain language. Select one to see what happened." />
      <div className="row-actions"><ClearHistory onCleared={(ids) => { historyRevision.current++; setAlerts((old) => old?.filter((a) => !ids.includes(a.alert_id))); setRevision((n) => n + 1); setNotice(`${ids.length} alert${ids.length === 1 ? "" : "s"} deleted.`); }} />{notice && <p className="dim" role="status">{notice}</p>}</div>
      {focused ? <>
        <div className="focus-banner"><p className="dim" role="status">{focused.length ? `Showing ${focused.length === 1 ? "the alert" : `${focused.length} alerts`} raised during your simulation.` : alerts === undefined && focus ? "Loading the simulation's alerts…" : ""}</p><a className="btn btn-sm" href="#/alerts">Show all alerts</a></div>
        {focused.length ? <div className="alert-list">{focused.map((a) => <AlertCard key={a.alert_id} alert={a} devices={devices} onOpen={onOpen} full />)}</div>
          : !focus ? <Empty icon="check" title="No alert from this simulation">The simulation finished, but Edge Watch did not raise an IDS alert, so no alert record exists for it.</Empty>
          : alerts !== undefined && <Empty icon="info" title="Simulation alerts not found">These alerts are no longer in the history. Show all alerts to see what remains.</Empty>}
      </> : <>
      <Card className="filters-card">
        <div className="filters">
          <label>Time<select value={filters.time} onChange={(e) => set("time", e.target.value)}><option value="all">All time</option><option value="hour">Last hour</option><option value="today">Today</option><option value="week">Last 7 days</option><option value="custom">Custom range</option></select></label>
          <div className="seg" role="group" aria-label="Severity">
            {["", "high", "medium", "low"].map((s) => <button key={s} className={filters.severity === s ? "on" : ""} aria-pressed={filters.severity === s} onClick={() => set("severity", s)}>{s ? `${s[0].toUpperCase()}${s.slice(1)}` : "All"}</button>)}
          </div>
          <label>Device / source<select value={filters.source} onChange={(e) => set("source", e.target.value)}><option value="">Any source</option>{selectableDevices.map((d) => <option key={d.key} value={d.key}>{d.name}</option>)}{filters.source && !selectableDevices.some((d) => d.key === filters.source) && <option value={filters.source}>{deviceName(devices, filters.source)}</option>}</select></label>
          {filters.time === "custom" && <><label>From<input type="date" value={filters.from} onChange={(e) => set("from", e.target.value)}/></label><label>To<input type="date" value={filters.to} onChange={(e) => set("to", e.target.value)}/></label></>}
          <button className="btn btn-sm" onClick={() => setFilters({ time: "all", from: "", to: "", severity: "", source: "" })}>Reset filters</button>
        </div>
      </Card>
      {alerts === undefined ? <p className="loading-line">Loading alerts…</p> : alerts === null ? <p className="warn">Alerts could not be loaded from the Edge Watch service.</p> : !alerts.length ? (
        <Empty icon="check" title="No alerts match these filters">Edge Watch has not raised an alert that fits this selection.</Empty>
      ) : (
        <>
          <p className="list-summary">{alerts.length} alerts · {counts.high} high · {counts.medium} medium · {counts.low} low</p>
          <div className="alert-list">{alerts.map((a) => <AlertCard key={a.alert_id} alert={a} devices={devices} onOpen={onOpen} full />)}</div>
        </>
      )}
      </>}
      <p className="note dim">Alerts describe observed traffic patterns; they are not proof of a device compromise.</p>
    </div>
  );
}
