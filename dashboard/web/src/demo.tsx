// Attack Simulator: runs a bounded lab attack against the user's smart home through the real API, narrated from the event stream only.
import { lazy, Suspense, useEffect, useRef, useState } from "react";
import { useHome } from "./home";
import { DeviceList, LayoutState, useAttacker, useLive } from "./smarthome";
import { AlertEvent, demoStages, Device, scenarioText, State } from "./store";
import { Card, detail, duration, Empty, fmt, Icon, PageHead, Pill, send, useNow } from "./ui";
import { json } from "./useStream";
const Home3D = lazy(() => import("./home3d"));
export type SimRun = { running: boolean; pid: number; started: number; ended?: number; planned_s: number; exit_code?: number | null; stopped_by_user?: boolean; out_dir?: string; request: { benign: string; families: string[]; mix?: string[] } };
export type SimStatus = { home_broker?: boolean; available: boolean; reason: string | null; port: number | null; running: SimRun | null; history: SimRun[]; families: { id: string; text: string; trained: boolean }[]; benign: string[]; limits: any };
/** Lab run status, polled every 2 s, and start/stop through the real API (which keeps its own limits). */

export function useSimulation() {
  const [status, setStatus] = useState<SimStatus | null | undefined>(undefined);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const poll = () => json<SimStatus>("/api/simulation").then(setStatus);
  useEffect(() => { poll(); const t = setInterval(poll, 2000); return () => clearInterval(t); }, []);
  async function act(path: string, body?: object) {
    setBusy(true);
    const r = await send(path, body);
    setError(r.ok ? null : `Refused (${r.status}): ${detail(r.data)}`);
    await poll();
    setBusy(false);
    return r.ok;
  }
  return { status, error, busy, act };
}
/** A run that ended badly on its own: not completed, and not stopped by the user. */
export const runFailed = (r?: SimRun | null) => !!r && !r.running && r.exit_code !== 0 && !r.stopped_by_user;
const ORDER = ["flood_publish", "bruteforce", "malformed", "flood_connect", "lowrate", "topic_probe", "wildcard"];

export type FlowStage = "pending" | "running" | "done" | "alert" | "warn";
export type FlowResult = "detected" | "missed" | "stopped" | "failed";
export const SETTLE_S = 10; // the IDS needs two 5 s windows; wait this long after a quiet run ends before calling it missed
const RESULT_LABEL: Record<FlowResult, string> = { detected: "Detected", missed: "Not detected", stopped: "Stopped", failed: "Failed" };

/** Ready → Attacking → Analyzing → Result, from API run status and stream events only. Alerts count only on this run's scheduled attack sources. */
export function simFlow(s: State, run: SimRun | null, now: number) {
  if (!run) return { stages: ["running", "pending", "pending", "pending"] as FlowStage[], result: null, alerts: [] as AlertEvent[], ttd: null, label: "Result" };
  const since = run.started, end = run.running ? now : run.ended ?? now;
  const st = demoStages(s, since, run.running ? now : Infinity);
  const markers = st.outcomes.map((o) => o.marker), sources = new Set(markers.map((m) => m.source_key).filter(Boolean));
  const alerts = s.alerts.filter((a) => sources.has(a.source_key) && a.start_ns / 1e9 >= since - 5 && a.start_ns / 1e9 <= end + 15);
  const ttds = st.outcomes.map((o) => o.ttd).filter((t): t is number => t != null);
  const result: FlowResult | null = alerts.length ? (run.running ? null : "detected") : runFailed(run) ? "failed" : run.running ? null : run.stopped_by_user || run.exit_code !== 0 ? "stopped" : now < end + SETTLE_S ? null : "missed";
  const attacking = st.begun > 0 && run.running && markers.some((m) => m.end_ns! / 1e9 > now);
  const stages: FlowStage[] = [
    st.begun || !run.running ? "done" : "running",
    !st.begun ? "pending" : attacking ? "running" : "done",
    !st.begun ? "pending" : result || alerts.length ? "done" : "running",
    alerts.length ? "alert" : result ? "warn" : "pending",
  ];
  return { stages, result, alerts, ttd: ttds.length ? Math.min(...ttds) : null, label: alerts.length ? "Detected" : result ? RESULT_LABEL[result] : "Result" };
}

const FLOW = [["Ready", "home"], ["Attacking", "attack"], ["Analyzing", "wave"]] as const;
function Flowchart({ stages, label }: { stages: FlowStage[]; label: string }) {
  return <ol className="flow" aria-label="Simulation progress">{[...FLOW, [label, stages[3] === "alert" ? "bell" : stages[3] === "warn" ? "info" : "shield"] as const].map(([name, icon], i) => (
    <li key={i} className={`flow-step flow-${stages[i]}`} aria-current={stages[i] === "running" ? "step" : undefined}>
      <span className="flow-dot"><Icon name={stages[i] === "done" ? "check" : icon} size={16} /></span><b>{name}</b>
      <span className="sr-only">{{ pending: "pending", running: "in progress", done: "complete", alert: "security alert", warn: "no alert" }[stages[i]]}</span>
    </li>))}</ol>;
}

// Each finished run opens its result popup once per browser tab, surviving remounts and reloads.
const seenResults = new Set<string>();
function firstShow(key: string) {
  let seen = seenResults.has(key);
  try { seen ||= sessionStorage.getItem(key) === "1"; sessionStorage.setItem(key, "1"); } catch { /* storage unavailable: the in-memory set still prevents repeats */ }
  seenResults.add(key);
  return !seen;
}
type Outcome = { result: FlowResult; name: string; ttd: number | null; alertIds: string[]; exit?: number | null };

function ResultModal({ outcome, onClose }: { outcome: Outcome | null; onClose: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => { const d = dialog.current; if (outcome && d && !d.open) { d.showModal(); d.querySelector<HTMLElement>(".btn-primary")?.focus(); } }, [outcome]); // showModal moves focus to the first button, so focus the main action after it
  const close = () => dialog.current?.close();
  const view = (ids: string[]) => { close(); location.hash = `/alerts?alerts=${ids.join(",")}`; };
  const o = outcome;
  const copy = !o ? null : {
    detected: { title: "Threat detected", text: "Edge Watch identified suspicious network activity." },
    missed: { title: "No security alert raised", text: "The simulation finished, but Edge Watch did not raise an alert." },
    stopped: { title: "Simulation stopped", text: "You stopped the attack before Edge Watch raised an alert." },
    failed: { title: "Simulation failed", text: `The attack lab exited with an error${o.exit != null ? ` (code ${o.exit})` : ""}. Check that Edge Watch is running and try again.` },
  }[o.result];
  return (
    <dialog ref={dialog} className={`card confirm-dialog result-modal result-${o?.result ?? ""}`} aria-labelledby="sim-result-title" aria-describedby="sim-result-text" onClose={onClose}>
      {o && copy && <>
        <p className="eyebrow">{o.name}</p>
        <h2 id="sim-result-title">{copy.title}</h2>
        <p id="sim-result-text">{copy.text}</p>
        {o.result === "detected" && o.ttd != null && <p className="result-ttd"><Icon name="clock" size={16} /><span>Alert after <b>{fmt(o.ttd)} s</b></span></p>}
        <div className="row-actions">
          <button className="btn" onClick={close}>Close</button>
          {o.result === "detected" && <button className="btn btn-primary" onClick={() => view(o.alertIds)}>View Alert Details</button>}
          {o.result === "missed" && <button className="btn btn-primary" onClick={() => view([])}>View Alerts</button>}
        </div>
      </>}
    </dialog>
  );
}

export function AttackSimulator({ state, devices, layout: layoutState }: { state: State; devices: Map<string, Device>; layout: LayoutState }) {
  const { status, error, busy, act } = useSimulation();
  const { devices: layout, loaded } = layoutState;
  const home = useHome();
  const now = useNow(1000);
  const live = useLive(state, layout, home, now);
  const attacker = useAttacker(state, now);
  const [family, setFamily] = useState("flood_publish");
  const [form, setForm] = useState({ episodes: 1, attack_s: 30, calm_s: 15, rate_factor: 1, seed: 1 });
  const dialog = useRef<HTMLDialogElement>(null);
  const set = (k: string, v: number) => setForm((f) => ({ ...f, [k]: v }));
  const total = 20 + form.episodes * (form.attack_s + form.calm_s);
  const max = status?.limits?.max_total_s ?? 600;
  const run = status?.running ?? null, last = status?.history?.[0] ?? null, active = run ?? last;
  const flow = simFlow(state, active, now);
  const [outcome, setOutcome] = useState<Outcome | null>(null);
  useEffect(() => {
    if (!active || active.running || !flow.result || now - (active.ended ?? now) > 300 || !firstShow(`ew-sim-result-${active.started}`)) return;
    const fams = active.request.families;
    setOutcome({ result: flow.result, name: fams.length === 1 ? scenarioText(fams[0]).name : `${fams.length} attack types`, ttd: flow.ttd, alertIds: flow.alerts.map((a) => a.alert_id), exit: active.exit_code });
  }, [flow.result, active?.started]);
  const families = [...(status?.families ?? [])].filter((f) => f.id !== "topic_probe").sort((a, b) => ORDER.indexOf(a.id) - ORDER.indexOf(b.id));
  if (status === undefined || !loaded) return <div className="page"><p className="loading-line">Loading the attack lab…</p></div>;
  return (
    <div className="page">
      <PageHead eyebrow="Attack Simulator" title="Attack your smart home" sub="Pick an attack, start it, and watch whether Edge Watch notices. Everything runs on this computer, for a fixed time."
        actions={<Pill tone="info" title={status?.limits?.target}>Local lab only · max {Math.round(max / 60)} min</Pill>} />
      {!status ? <Empty icon="plug" title="The attack lab cannot be reached">The Edge Watch service did not answer. It retries automatically.</Empty> : !status.available ? (
        <Empty icon="plug" title="The attack lab is not available">{status.reason} Start Edge Watch with <code>.\scripts\start-edgewatch.ps1 -Mode dashboard</code>.</Empty>
      ) : (
        <>
          <SimProgress run={active} flow={flow} now={now} />
          <div className="atk-grid">
          <Card title="Choose an attack" className="atk-setup">
            <div className="scenarios" role="radiogroup" aria-label="Attack">
              {families.map((f) => (
                <button type="button" key={f.id} role="radio" aria-checked={family === f.id} disabled={!!run} className={`scenario ${family === f.id ? "on" : ""}`} onClick={() => setFamily(f.id)}>
                  <span className="sc-name">{scenarioText(f.id).name}{f.id === "wildcard" && <Pill tone="info">Rule based</Pill>}</span>
                  <span className="sc-text">{scenarioText(f.id).text}</span>
                </button>
              ))}
            </div>
            <div className="demo-actions">
              {run ? <button className="btn btn-danger btn-lg" type="button" onClick={() => act("/api/simulation/stop")} disabled={busy}><Icon name="stop" size={18}/>Stop Attack</button>
                : <button className="btn btn-primary btn-lg" disabled={busy} onClick={() => dialog.current?.showModal()}><Icon name="play" size={18}/>Start Attack</button>}
            </div>
            {error && <p className="warn" role="status">{error}</p>}
          </Card>
          <div className="atk-right">
            <Card title="Your home under attack" sub={attacker ? (attacker.active ? "A simulated attack is in progress" : "The attack has ended") : "No attack running"} className="floor-card">
              <div className="floor-wrap"><Suspense fallback={<p>Loading your home…</p>}><Home3D devices={layout} live={live} attacker={attacker} fallback={<DeviceList devices={layout} live={live}/>} /></Suspense></div>
            </Card>
          </div>
          </div>
          <dialog ref={dialog} className="sim-config card" aria-labelledby="sim-config-title" onCancel={(e) => { if (busy || run) e.preventDefault(); }}>
            <form onSubmit={async (e) => { e.preventDefault(); if (total > max || form.attack_s < 10 || form.attack_s > 120 || form.calm_s < 5 || form.calm_s > 60 || form.episodes < 1 || form.episodes > 3 || form.rate_factor < .05 || form.rate_factor > 1 || form.seed < 0 || form.seed > 1000000) return; if (await act("/api/simulation/start", { benign: "layout", families: [family], ...form })) dialog.current?.close(); }}>
              <p className="eyebrow">Simulation setup</p><h2 id="sim-config-title">Configure {scenarioText(family).name}</h2>
              <p className="dim">Target: local smart-home hub. The simulation stays within the lab safety limits.</p>
              <div className="filters sim-fields">
                <label>Attack duration (seconds)<input type="number" min="10" max="120" required value={form.attack_s} onChange={(e) => set("attack_s", +e.target.value)}/></label>
                <label>Intensity: {Math.round(form.rate_factor * 100)}%<input type="range" min="0.05" max="1" step="0.05" value={form.rate_factor} onChange={(e) => set("rate_factor", +e.target.value)}/></label>
                <label>Repeats<input type="number" min="1" max="3" required value={form.episodes} onChange={(e) => set("episodes", +e.target.value)}/></label>
                <label>Gap between repeats (seconds)<input type="number" min="5" max="60" required value={form.calm_s} onChange={(e) => set("calm_s", +e.target.value)}/></label>
              </div>
              <details className="more"><summary>Advanced settings</summary><label>Random seed<input type="number" min="0" max="1000000" value={form.seed} onChange={(e) => set("seed", +e.target.value)}/></label></details>
              <p className={total > max ? "warn" : "dim"}>Estimated total: {duration(total)}{total > max ? ` — maximum is ${duration(max)}` : ""}.</p>
              {error && <p className="warn" role="alert">{error}</p>}
              <div className="row-actions"><button type="button" className="btn" disabled={busy} onClick={() => dialog.current?.close()}>Cancel</button><button type="submit" className="btn btn-primary" disabled={busy || !!run || total > max}>{busy ? "Starting…" : "Launch Simulation"}</button></div>
            </form>
          </dialog>
        </>
      )}
      <ResultModal outcome={outcome} onClose={() => setOutcome(null)} />
    </div>
  );
}

/** Compact flowchart plus a one-line summary of the current or last run. Details live on the Alerts page. */
function SimProgress({ run, flow, now }: { run: SimRun | null; flow: ReturnType<typeof simFlow>; now: number }) {
  const fams = run?.request.families ?? [];
  const name = !run ? "No simulation yet" : fams.length === 1 ? scenarioText(fams[0]).name : `${fams.length} attack types`;
  const finish = !run ? "Pick an attack and start it" : run.running ? `Running · ${duration(Math.max(0, now - run.started))} of about ${duration(run.planned_s)}` : runFailed(run) ? "Simulation failed" : run.stopped_by_user || run.exit_code !== 0 ? "Stopped by you" : "Simulation completed";
  return (
    <Card className="flow-card">
      <Flowchart stages={flow.stages} label={flow.label} />
      <p className="flow-summary" role="status"><b>{name}</b><span>{finish}</span>{flow.alerts.length > 0 && <span className="c-bad">{flow.ttd != null ? `Alert after ${fmt(flow.ttd)} s` : "Alert raised"}</span>}{flow.result === "missed" && <span className="warn">No alert raised</span>}</p>
    </Card>
  );
}
