// Attack Simulator: runs a bounded lab attack against the user's smart home through the real API, narrated from the event stream only.
import { useEffect, useState } from "react";
import { deviceName } from "./alerts";
import { homeLink, useHome } from "./home";
import { ActivityChart } from "./overview";
import { FloorPlan, LayoutState, useAttacker, useLive } from "./smarthome";
import { demoStages, Device, episodeOutcomes, percentile, scenarioText, State } from "./store";
import { Card, clock, detail, duration, Empty, fmt, Icon, PageHead, Pill, send, useNow } from "./ui";
import { json } from "./useStream";

type SimRun = { running: boolean; pid: number; started: number; ended?: number; planned_s: number; exit_code?: number | null; stopped_by_user?: boolean; out_dir?: string; request: { benign: string; families: string[]; mix?: string[] } };
export type SimStatus = { home_broker?: boolean; available: boolean; reason: string | null; port: number | null; running: SimRun | null; history: SimRun[]; families: { id: string; text: string; trained: boolean }[]; benign: string[]; limits: any };
type Step = { label: string; sub: string; state: "done" | "active" | "pending" | "missed" | "skip" };

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
  }
  return { status, error, busy, act };
}

/** A run that ended badly on its own: not completed, and not stopped by the user. */
export const runFailed = (r?: SimRun | null) => !!r && !r.running && r.exit_code !== 0 && !r.stopped_by_user;

const ORDER = ["flood_publish", "bruteforce", "malformed", "flood_connect", "lowrate", "topic_probe", "wildcard"];

export function AttackSimulator({ state, devices, layout: layoutState }: { state: State; devices: Map<string, Device>; layout: LayoutState }) {
  const { status, error, busy, act } = useSimulation();
  const { devices: layout, loaded } = layoutState;
  const home = useHome();
  const now = useNow(1000);
  const live = useLive(state, layout, home, now);
  const attacker = useAttacker(state, now);
  const [family, setFamily] = useState("flood_publish");
  const [form, setForm] = useState({ episodes: 1, attack_s: 30, calm_s: 15, rate_factor: 1, seed: 1 });
  const set = (k: string, v: number) => setForm((f) => ({ ...f, [k]: v }));
  const software = layout.filter((d) => d.source === "software"), wokwi = layout.length - software.length, wokwiLive = homeLink(home) === "online";
  const online = software.filter((d) => home?.devices?.[d.id]?.status === "online").length;
  const total = 20 + form.episodes * (form.attack_s + form.calm_s);
  const max = status?.limits?.max_total_s ?? 600;
  const run = status?.running ?? null, last = status?.history?.[0] ?? null, active = run ?? last;
  const families = [...(status?.families ?? [])].sort((a, b) => ORDER.indexOf(a.id) - ORDER.indexOf(b.id));
  if (status === undefined || !loaded) return <div className="page"><p className="loading-line">Loading the attack lab…</p></div>;
  return (
    <div className="page">
      <PageHead eyebrow="Attack Simulator" title="Attack your smart home" sub="Pick an attack, start it, and watch whether Edge Watch notices. Everything runs on this computer, for a fixed time."
        actions={<Pill tone="info" title={status?.limits?.target}>Local lab only · max {Math.round(max / 60)} min</Pill>} />
      {!status ? <Empty icon="plug" title="The attack lab cannot be reached">The Edge Watch service did not answer. It retries automatically.</Empty> : !status.available ? (
        <Empty icon="plug" title="The attack lab is not available">{status.reason} Start Edge Watch with <code>.\scripts\start-edgewatch.ps1 -Mode dashboard</code>.</Empty>
      ) : (
        <div className="atk-grid">
          <Card title="1. Choose an attack" className="atk-setup">
            <div className="scenarios" role="radiogroup" aria-label="Attack">
              {families.map((f) => (
                <button type="button" key={f.id} role="radio" aria-checked={family === f.id} disabled={!!run} className={`scenario ${family === f.id ? "on" : ""}`} onClick={() => setFamily(f.id)}>
                  <span className="sc-name">{scenarioText(f.id).name}{!f.trained && <Pill tone="warn">Not trained</Pill>}</span>
                  <span className="sc-text">{scenarioText(f.id).text}</span>
                </button>
              ))}
            </div>
            <h3>2. Target</h3>
            <div className="target-box">
              <Icon name="hub" size={20} />
              <div><b>Your smart-home hub, and so every device on it</b>
                <p className="dim">In MQTT every device talks through one hub, so these attacks aim at the hub. The traffic comes from a separate simulated attacker, shown outside the house, not from your devices.</p></div>
            </div>
            <h3>3. Your home during the attack</h3>
            <p className="dim">{!layout.length ? <>Your home is empty, so only the attacker will send traffic. Build a home on the Smart Home page first.</> : home?.running ? <>{online} of {software.length} software devices are online and keep working during the attack{wokwi ? <>, plus {wokwi} Wokwi device{wokwi > 1 ? "s" : ""} ({wokwiLive ? "connected" : "not connected: start the Wokwi simulator"})</> : ""}.</> : <>The smart-home hub is stopped, so your devices are offline and only the attacker will send traffic. Start the hub on the Smart Home page first.</>}</p>
            <details className="more">
              <summary>Customize</summary>
              <div className="filters">
                <label>Attack length (s)<input type="number" min={10} max={120} value={form.attack_s} onChange={(e) => set("attack_s", +e.target.value)} disabled={!!run} /></label>
                <label>Calm gap after (s)<input type="number" min={5} max={60} value={form.calm_s} onChange={(e) => set("calm_s", +e.target.value)} disabled={!!run} /></label>
                <label>Repeats<input type="number" min={1} max={3} value={form.episodes} onChange={(e) => set("episodes", +e.target.value)} disabled={!!run} /></label>
                <label>Intensity: {Math.round(form.rate_factor * 100)}% of the lab default<input type="range" min={0.05} max={1} step={0.05} value={form.rate_factor} onChange={(e) => set("rate_factor", +e.target.value)} disabled={!!run} /></label>
                <label>Random seed<input type="number" min={0} max={1000000} value={form.seed} onChange={(e) => set("seed", +e.target.value)} disabled={!!run} /></label>
              </div>
            </details>
            <p className={total > max ? "warn" : "dim"}>About {duration(total)} in total{total > max ? `, over the ${duration(max)} limit` : ""}.</p>
            <div className="demo-actions">
              <button className="btn btn-primary btn-lg" disabled={busy || !!run || total > max} onClick={() => act("/api/simulation/start", { benign: "layout", families: [family], ...form })}><Icon name="play" size={18} />{run ? "Running" : "Start attack"}</button>
              <button className="btn btn-danger" type="button" onClick={() => act("/api/simulation/stop")} disabled={busy || !run}><Icon name="stop" size={16} />Stop</button>
            </div>
            {error && <p className="warn" role="status">{error}</p>}
          </Card>
          <div className="atk-right">
            <Card title="Your home under attack" sub={attacker ? (attacker.active ? "A simulated attack is in progress" : "The attack has ended") : "No attack running"} className="floor-card">
              <div className="floor-wrap"><FloorPlan devices={layout} live={live} attacker={attacker} /></div>
            </Card>
            {active ? <DemoLive state={state} devices={devices} run={run} last={last} now={now} /> : (
              <Card title="What you will see">
                <ol className="steps">{["Normal activity", "Attack begins", "Suspicious traffic observed", "Alert raised"].map((s, i) => <li key={s} className="step step-pending"><span className="step-dot">{i + 1}</span><span><b>{s}</b><span>{["Your devices exchange everyday messages.", "A simulated attacker joins the network.", "Edge Watch notices traffic that looks unlike normal devices.", "If the pattern continues, Edge Watch raises an alert you can open."][i]}</span></span></li>)}</ol>
                <p className="note dim">Every stage lights up only when the real event stream shows it. If Edge Watch misses an attack, this says so.</p>
              </Card>
            )}
          </div>
        </div>
      )}
      {(status?.available ?? false) && <ActivityChart state={state} title="Live network activity" sub="Shaded periods are when a simulated attack was scheduled" />}
      <SessionAttacks state={state} devices={devices} now={now} />
    </div>
  );
}

function DemoLive({ state, devices, run, last, now }: { state: State; devices: Map<string, Device>; run: SimRun | null; last: SimRun | null; now: number }) {
  const active = (run ?? last)!, since = active.started, end = run ? now : active.ended ?? now;
  const families = active.request.families, attack = families.length > 0;
  const st = demoStages(state, since, run ? now : Infinity);
  const inPeriod = state.alerts.filter((a) => a.start_ns / 1e9 >= since - 5 && a.start_ns / 1e9 <= end + 15);
  const ttds = st.outcomes.map((o) => o.ttd).filter((t): t is number => t != null);
  const missed = st.outcomes.filter((o) => !o.alert && (run ? o.marker.end_ns! / 1e9 + 15 < now : true)).length;
  const name = !attack ? "Normal home activity" : families.length === 1 ? scenarioText(families[0]).name : `${families.length} attack types`;
  const steps: Step[] = [{ label: "Normal activity", sub: st.normal ? "Virtual devices are exchanging everyday messages" : "Waiting for the first traffic", state: st.normal ? "done" : run ? "active" : "pending" }];
  if (attack) {
    const first = state.markers.filter((m) => m.marker === "scheduled_attack" && m.start_ns! / 1e9 >= since - 1).sort((a, b) => a.start_ns! - b.start_ns!)[0];
    steps.push(
      { label: "Attack begins", sub: st.begun ? `${st.begun} of ${st.scheduled} simulated attacks started` : first ? `First attack at ${clock(first.start_ns! / 1e9)}` : "Waiting for the attack schedule", state: st.begun ? "done" : run ? "active" : "pending" },
      { label: "Suspicious traffic observed", sub: st.suspicious ? "Edge Watch flagged traffic from the attacker" : st.begun ? (run ? "Watching the attacker's traffic" : "Nothing suspicious was flagged") : "Not yet", state: st.suspicious ? "done" : st.begun ? (run ? "active" : "missed") : "pending" },
      { label: "Alert raised", sub: st.alerted ? `${st.alerted} of ${st.begun} attacks alerted${ttds.length ? `, first after ${fmt(Math.min(...ttds))} s` : ""}` : st.begun && !run ? "No alert was raised for this attack" : "Waiting for consecutive suspicious checks", state: st.alerted ? (missed ? "missed" : "done") : st.begun ? (run ? "active" : "missed") : "pending" },
    );
  } else steps.push({ label: "No alerts expected", sub: inPeriod.length ? `${inPeriod.length} alert${inPeriod.length > 1 ? "s" : ""} raised during normal traffic: false alarms` : "None raised so far", state: inPeriod.length ? "missed" : run ? "active" : "done" });
  const elapsed = Math.max(0, now - since);
  if (!run && runFailed(active)) return <Card title="Last run failed" sub={name}><p className="warn">The lab run ended with an error (exit code {active.exit_code}) after {duration((active.ended ?? since) - since)}, so no result is shown. Details: runner.log in the lab folder {active.out_dir}.</p></Card>;
  return (
    <Card title={run ? "Demo in progress" : "Last demo"} sub={name} className="demo-live" actions={run ? <Pill tone="info"><span className="live-dot" />Running</Pill> : <Pill tone={active.exit_code === 0 ? "ok" : "warn"}>{active.exit_code === 0 ? "Completed" : "Stopped by you"}</Pill>}>
      {run && (
        <div className="progress" role="progressbar" aria-valuemin={0} aria-valuemax={run.planned_s} aria-valuenow={Math.round(elapsed)} aria-label="Demo progress">
          <div className="progress-track"><i style={{ width: `${Math.min(100, (elapsed / run.planned_s) * 100)}%` }} /></div>
          <span>{duration(elapsed)} of about {duration(run.planned_s)}</span>
        </div>
      )}
      <ol className="steps">{steps.map((s, i) => <li key={s.label} className={`step step-${s.state}`}><span className="step-dot">{s.state === "done" ? <Icon name="check" size={14} /> : s.state === "missed" ? "!" : i + 1}</span><span><b>{s.label}</b><span>{s.sub}</span></span></li>)}</ol>
      {!run && (
        <div className="result">
          <h3>Results</h3>
          <dl className="result-grid">
            {attack && <div><dt>Attacks scheduled</dt><dd>{st.scheduled}</dd></div>}
            <div><dt>Alerts raised</dt><dd>{inPeriod.length}</dd></div>
            {attack && <div><dt>Matched to the attacks</dt><dd>{inPeriod.filter((a) => a.status === "matches_scheduled_attack").length}</dd></div>}
            {attack && <div><dt>Typical response time</dt><dd>{ttds.length ? `${fmt(percentile(ttds, 0.5))} s` : "—"}</dd></div>}
            {attack && <div className={missed ? "bad" : ""}><dt>Missed attacks</dt><dd>{missed}</dd></div>}
            {!attack && <div className={inPeriod.length ? "bad" : ""}><dt>False alarms</dt><dd>{inPeriod.length}</dd></div>}
          </dl>
          <p className="note dim">A simulated attack in a local lab, not a real-world incident. Response time runs from the attack's scheduled start to the alert.</p>
        </div>
      )}
      {st.outcomes.length > 0 && (
        <ul className="outcomes">{st.outcomes.map((o, i) => (
          <li key={i}><Icon name={o.alert ? "check" : "clock"} size={16} /><span><b>{scenarioText(o.marker.family ?? "").name}</b> · {deviceName(devices, o.marker.source_key ?? "")} · {clock(o.marker.start_ns! / 1e9)}</span>
            <span className={o.alert ? "c-good" : now * 1e9 < o.marker.end_ns! + 15e9 ? "dim" : "c-bad"}>{o.alert ? `Alert after ${fmt(o.ttd)} s` : now * 1e9 < o.marker.end_ns! + 15e9 ? "Watching…" : "No alert raised"}</span></li>
        ))}</ul>
      )}
    </Card>
  );
}

function SessionAttacks({ state, devices, now }: { state: State; devices: Map<string, Device>; now: number }) {
  const outcomes = episodeOutcomes(state);
  if (!outcomes.length) return null;
  return (
    <details className="card more-card">
      <summary>All simulated attacks in this monitoring session ({outcomes.length})</summary>
      <div className="scroll-x">
        <table>
          <thead><tr><th>Attack</th><th>Device</th><th>Started</th><th>Result</th><th className="r">Time to alert</th></tr></thead>
          <tbody>{outcomes.map((o, i) => <tr key={i}><td>{scenarioText(o.marker.family ?? "").name}</td><td>{deviceName(devices, o.marker.source_key ?? "")}</td><td className="num">{clock(o.marker.start_ns! / 1e9)}</td><td>{o.alert ? <span className="c-good">Alert raised · {o.alert.severity}</span> : now * 1e9 < o.marker.end_ns! ? <span className="dim">Running</span> : <span className="c-bad">No alert raised</span>}</td><td className="r num">{o.ttd == null ? "—" : `${fmt(o.ttd)} s`}</td></tr>)}</tbody>
        </table>
      </div>
      <p className="note dim">Attack types the AI was not trained on (listening to every device, topic exploration) may only raise a low-severity rule alert or none at all. That is a measured limit, not a fault in this view.</p>
    </details>
  );
}
