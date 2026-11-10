import "@fontsource-variable/inter";
import "@fontsource-variable/jetbrains-mono";
import { useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import { AlertsPage, IncidentDrawer, deviceName } from "./alerts";
import { AttackSimulator } from "./demo";
import { TYPES } from "./devices";
import { SmartHomePage, useLayout } from "./smarthome";
import { Activity, AlertEvent, classText, deviceDirectory, networkActivity, overview, provenanceState, State } from "./store";
import { fmt, Icon, useNow } from "./ui";
import { deviceSummary, Home, useHome } from "./home";
import { ALERT_HISTORY_CLEARED, Health, useStream } from "./useStream";
import "./styles.css";

const NAV: [string, string, string][] = [["home", "Smart Home", "home"], ["attack", "Attack Simulator", "attack"], ["alerts", "Alerts", "bell"]];
const ALIAS: Record<string, string> = { overview: "home", demo: "attack" }; // earlier links keep working; anything else, such as #/advanced, opens Smart Home

// Hash routes keep deep links working with the API's single-page fallback: #/home, #/attack, #/alerts?source=<key>.
function parse() {
  const [path, query] = location.hash.replace(/^#\/?/, "").split("?");
  const parts = (path || "home").split("/");
  parts[0] = ALIAS[parts[0]] ?? parts[0];
  const top = NAV.some(([id]) => id === parts[0]) ? parts[0] : "home";
  return { top, params: new URLSearchParams(query) };
}

function App() {
  const { state, connected, loading, health, apiDown } = useStream();
  const [route, setRoute] = useState(parse);
  const [notice, setNotice] = useState<AlertEvent | null>(null);
  const seenAlerts = useRef<Set<string> | null>(null);
  const [open, setOpen] = useState<AlertEvent | null>(null);
  const layoutState = useLayout(), layout = layoutState.devices;
  const home = useHome(), now = useNow(2000);
  const activity = networkActivity(state, health, connected, now);
  const devices = useMemo(() => deviceDirectory(state, layout.map((d) => ({ id: d.id, name: d.name, icon: TYPES[d.type].icon }))), [state.markers, state.order, layout]);
  const go = (r: string) => { location.hash = `/${r}`; };
  useEffect(() => { const on = () => { setRoute(parse()); window.scrollTo(0, 0); }; window.addEventListener("hashchange", on); return () => window.removeEventListener("hashchange", on); }, []);
  const alert = open ? state.alerts.find((a) => a.alert_id === open.alert_id) ?? open : null; // live updates extend an open alert

  useEffect(() => {
    const cleared = (event: Event) => {
      const ids: unknown = (event as CustomEvent).detail;
      if (!Array.isArray(ids)) return;
      setOpen((a) => a && ids.includes(a.alert_id) ? null : a);
      setNotice((a) => a && ids.includes(a.alert_id) ? null : a);
    };
    window.addEventListener(ALERT_HISTORY_CLEARED, cleared);
    return () => window.removeEventListener(ALERT_HISTORY_CLEARED, cleared);
  }, []);

  useEffect(() => {
    const key = (e: KeyboardEvent) => {
      if (["INPUT", "SELECT", "TEXTAREA"].includes((e.target as HTMLElement).tagName)) return;
      if (e.key === "Escape") setOpen(null);
      if ((e.key === "ArrowDown" || e.key === "ArrowUp") && open && state.alerts.length) {
        e.preventDefault();
        const ordered = [...state.alerts].sort((a, b) => b.start_ns - a.start_ns);
        const at = ordered.findIndex((a) => a.alert_id === open.alert_id);
        setOpen(ordered[at < 0 ? 0 : (at + (e.key === "ArrowDown" ? 1 : -1) + ordered.length) % ordered.length]);
      }
    };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, [state.alerts, open]);

  useEffect(() => {
    if (loading) return;
    const ids = new Set(state.alerts.map(a => a.alert_id));
    if (seenAlerts.current && connected && state.provenances[0] === "live") {
      const fresh = state.alerts.find(a => !seenAlerts.current!.has(a.alert_id) && Date.now() / 1000 - a.last_window_ns / 1e9 < 60);
      if (fresh) setNotice(fresh);
    }
    seenAlerts.current = ids;
  }, [state.alerts, loading, connected]);
  const offline = !connected && !loading;
  return (
    <div className={`app ${offline ? "frozen" : ""}`}>
      {provenanceState(state) === "error" && <div className="provenance-error" role="alert">Provenance unknown – do not present</div>}
      <header className="topbar">
        <a className="brand" href="#/home" aria-label="Edge Watch home">
          <span className="logo"><svg width="20" height="20" viewBox="0 0 16 16" aria-hidden="true"><path d="M8 1 15 8 8 15 1 8Z" fill="none" stroke="currentColor" strokeWidth="1.6" /><circle cx="8" cy="8" r="1.8" fill="currentColor" /></svg></span>
          <span>Edge Watch</span>
        </a>
        <nav className="nav" aria-label="Main">
          {NAV.map(([id, label, icon]) => <button key={id} className={`tab ${route.top === id ? "tab-on" : ""}`} aria-current={route.top === id ? "page" : undefined} onClick={() => go(id)}><Icon name={icon} size={18} /><span>{label}</span></button>)}
        </nav>
        <div className="top-status"><span className="lab-tag" title="All devices and attacks are software on this computer">Simulated lab</span></div>
      </header>
      {!loading && <GlobalStatus state={state} health={health} connected={connected} home={home} activity={activity} />}
      {offline && <div className="disconnect" role="status">Connection to Edge Watch lost{state.lastTs ? ` – last update ${new Date(state.lastTs * 1000).toLocaleTimeString([], { hour12: false })}` : ""}. {apiDown ? "The service is unreachable; retrying." : "Reconnecting."}</div>}
      {loading ? (
        <main className="loading"><div className="scan" /><p>Connecting to Edge Watch…</p></main>
      ) : (
        <main key={route.top}>
          {route.top === "attack" ? <AttackSimulator state={state} devices={devices} layout={layoutState} />
            : route.top === "alerts" ? <AlertsPage state={state} devices={devices} onOpen={setOpen} source={route.params.get("source") ?? undefined} focus={route.params.get("alerts") ?? undefined} />
            : <SmartHomePage state={state} devices={devices} layout={layoutState} onOpen={setOpen} go={go} activity={activity} />}
        </main>
      )}
      {notice && <aside className="security-toast" role="status" aria-live="polite"><b>{classText(notice.predicted_class).title}</b><p>{deviceName(devices, notice.source_key)} · {notice.severity} severity · {new Date(notice.start_ns / 1e6).toLocaleTimeString()}</p><div className="row-actions"><button className="btn btn-sm" onClick={() => { setOpen(notice); setNotice(null); }}>Inspect alert</button><button className="btn btn-sm" onClick={() => { go("home"); setNotice(null); }}>View home network</button><button className="btn btn-sm" onClick={() => setNotice(null)}>Dismiss</button></div></aside>}
      {alert && <IncidentDrawer alert={alert} state={state} devices={devices} onClose={() => setOpen(null)} />}
    </div>
  );
}

createRoot(document.getElementById("root")!).render(<App />);

function GlobalStatus({ state, health, connected, home, activity }: { state: State; health: Health | null; connected: boolean; home: Home | null; activity: Activity }) {
  const stats = overview(state), provenance = provenanceState(state);
  const monitor = provenance === "error" || health?.status === "no_store" ? "Error" : !connected || !health ? "Offline" : health.ids_enabled === false ? "Paused" : health.ids === "running" ? "Active" : "Offline";
  const tone = monitor === "Active" ? "ok" : monitor === "Paused" ? "warn" : "bad";
  const devices = deviceSummary(home);
  return <section className="global-status" aria-label="Security summary">
    <div className={`global-stat global-${tone}`}><span className="global-icon"><Icon name="shield" size={18}/></span><span className="global-copy"><b>{monitor}</b><small>Monitoring</small></span></div>
    <div className="global-stat"><span className="global-icon"><Icon name="home" size={18}/></span><span className="global-copy"><b>{devices.online} <small>of {devices.total}</small></b><small>Devices online</small></span></div>
    <div className="global-stat"><span className="global-icon"><Icon name="bell" size={18}/></span><span className="global-copy"><b>{health?.alerts_total ?? "—"}</b><small>Security alerts{stats.alerts ? ` · ${stats.alerts} this session` : ""}</small></span></div>
    <div className={`global-stat${activity.status === "Receiving" || activity.status === "No recent traffic" ? "" : " global-warn"}`}><span className="global-icon"><Icon name="wave" size={18}/></span><span className="global-copy"><b>{activity.rate == null ? "—" : fmt(activity.rate, 1)} <small>{activity.rate == null ? "" : "msg/s · 10 s mean"}</small></b><small>Broker MQTT activity · {activity.status}</small></span></div>
  </section>;
}
