import "@fontsource-variable/inter";
import "@fontsource-variable/jetbrains-mono";
import { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import { AlertsPage, IncidentDrawer } from "./alerts";
import { AttackSimulator } from "./demo";
import { TYPES } from "./devices";
import { SmartHomePage, useLayout } from "./smarthome";
import { AlertEvent, alertOrder, deviceDirectory, provenanceState } from "./store";
import { Icon, Pill } from "./ui";
import { useStream } from "./useStream";
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
  const [open, setOpen] = useState<AlertEvent | null>(null);
  const layoutState = useLayout(), layout = layoutState.devices;
  const devices = useMemo(() => deviceDirectory(state, layout.map((d) => ({ id: d.id, name: d.name, icon: TYPES[d.type].icon }))), [state.markers, state.order, layout]);
  const ordered = useMemo(() => alertOrder(state.alerts), [state.alerts]);
  const go = (r: string) => { location.hash = `/${r}`; };
  useEffect(() => { const on = () => { setRoute(parse()); window.scrollTo(0, 0); }; window.addEventListener("hashchange", on); return () => window.removeEventListener("hashchange", on); }, []);
  const alert = open ? state.alerts.find((a) => a.alert_id === open.alert_id) ?? open : null; // live updates extend an open alert

  useEffect(() => {
    const key = (e: KeyboardEvent) => {
      if (["INPUT", "SELECT", "TEXTAREA"].includes((e.target as HTMLElement).tagName)) return;
      if (e.key === "Escape") setOpen(null);
      if ((e.key === "ArrowDown" || e.key === "ArrowUp") && open && ordered.length) {
        e.preventDefault();
        const at = ordered.findIndex((a) => a.alert_id === open.alert_id);
        setOpen(ordered[at < 0 ? 0 : (at + (e.key === "ArrowDown" ? 1 : -1) + ordered.length) % ordered.length]);
      }
    };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, [ordered, open]);

  const offline = !connected && !loading;
  const provenance = state.provenances[0];
  const live = offline ? <Pill tone="bad">Offline</Pill> : provenance === "live" ? <Pill tone="ok"><span className="live-dot" />Live</Pill> : provenance === "replay" ? <Pill tone="info" title="Recorded traffic played back, not live">Replay</Pill> : provenance === "synthetic" ? <Pill tone="muted">Synthetic</Pill> : <Pill tone="muted">No data yet</Pill>;
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
        <div className="top-status"><span className="lab-tag" title="All devices and attacks are software on this computer">Simulated lab</span>{live}</div>
      </header>
      {offline && <div className="disconnect" role="status">Connection to Edge Watch lost{state.lastTs ? ` – last update ${new Date(state.lastTs * 1000).toLocaleTimeString([], { hour12: false })}` : ""}. {apiDown ? "The service is unreachable; retrying." : "Reconnecting."}</div>}
      {loading ? (
        <main className="loading"><div className="scan" /><p>Connecting to Edge Watch…</p></main>
      ) : (
        <main key={route.top}>
          {route.top === "attack" ? <AttackSimulator state={state} devices={devices} layout={layoutState} />
            : route.top === "alerts" ? <AlertsPage state={state} devices={devices} onOpen={setOpen} source={route.params.get("source") ?? undefined} />
            : <SmartHomePage state={state} health={health} connected={connected} devices={devices} layout={layoutState} onOpen={setOpen} go={go} />}
        </main>
      )}
      {alert && <IncidentDrawer alert={alert} state={state} devices={devices} onClose={() => setOpen(null)} />}
    </div>
  );
}

createRoot(document.getElementById("root")!).render(<App />);
