// Virtual Smart Home: the Wokwi ESP32's own readings, relayed by lab.home's bridge. Nothing here is estimated or generated.
import { useEffect, useState } from "react";
import { ago, Card, detail, Icon, Pill, send } from "./ui";
import { json } from "./useStream";

type Reading<T> = { value: T; ts: number } | undefined;
export type DeviceReport = { state: Record<string, any> | null; status: "online" | "offline" | null; events: { event: string; at: number; result?: string; level?: number }[]; ts: number | null };
export type Home = { configured: boolean; running?: boolean; transport?: "serial" | "gateway"; devices?: Record<string, DeviceReport>; port?: number; monitored_port?: number | null; now?: number; bridge_connected?: boolean; rejected?: number;
  values?: { temperature?: Reading<number>; humidity?: Reading<number>; motion?: Reading<boolean>; light?: Reading<boolean>; status?: Reading<string> } };

const STALE_S = 30; // the firmware reports every 10 s

export function useHome() {
  const [home, setHome] = useState<Home | null>(null);
  useEffect(() => { let live = true; const poll = () => json<Home>("/api/home").then((h) => live && setHome(h)); poll(); const t = setInterval(poll, 2000); return () => { live = false; clearInterval(t); }; }, []);
  return home;
}

/** Device connectivity from the device's own retained status and last-will message, plus how fresh its last reading is. */
export function homeLink(h: Home | null): "absent" | "broker_down" | "waiting" | "online" | "stale" | "offline" {
  if (!h?.configured) return "absent";
  if (!h.running) return "broker_down";
  const v = h.values ?? {}, status = v.status?.value, latest = Math.max(0, ...Object.values(v).map((r) => r?.ts ?? 0));
  if (!status) return "waiting";
  if (status === "offline") return "offline";
  return h.now! - latest > STALE_S ? "stale" : "online";
}

const LINK_TEXT = { online: ["Connected", "ok"], stale: ["No recent readings", "warn"], offline: ["Disconnected", "bad"], waiting: ["Waiting for the device", "muted"], broker_down: ["Hub not running", "warn"], absent: ["", "muted"] } as const;

export function HomeCard({ home, compact = false }: { home: Home | null; compact?: boolean }) {
  const [pending, setPending] = useState<boolean | null>(null);
  const [error, setError] = useState<string | null>(null);
  const link = homeLink(home);
  if (compact) {
    if (link === "absent") return <div className="wokwi-mini"><b>Wokwi ESP32</b><p className="dim">Not set up. Run <code>.\scripts\start-wokwi-home.ps1</code>, then start the simulator in VS Code, to add a device with real sensor readings.</p></div>;
    const [text, t] = LINK_TEXT[link];
    return <div className="wokwi-mini"><b>Wokwi ESP32</b> <Pill tone={t}>{link === "online" && <span className="live-dot" />}{text}</Pill><p className="dim">{home?.transport === "serial" ? "Readings arrive over a serial link; Edge Watch's bridge publishes them over MQTT." : "Connects over the Wokwi gateway."}</p></div>;
  }
  const v = home?.values ?? {}, now = home?.now ?? Date.now() / 1000;
  useEffect(() => { if (pending !== null && v.light?.value === pending) setPending(null); }, [v.light?.value, pending]);
  if (link === "absent") return null;
  const [linkText, tone] = LINK_TEXT[link];
  const live = link === "online";
  async function toggle() {
    const on = !(v.light?.value ?? false);
    setPending(on);
    const r = await send("/api/home/light", { on });
    if (!r.ok) { setPending(null); setError(`Command refused (${r.status}): ${detail(r.data)}`); } else setError(null);
  }
  const tiles = [
    { icon: "thermo", label: "Temperature", value: v.temperature ? `${v.temperature.value.toFixed(1)} °C` : "—", at: v.temperature?.ts },
    { icon: "wave", label: "Humidity", value: v.humidity ? `${v.humidity.value.toFixed(0)} %` : "—", at: v.humidity?.ts },
    { icon: "motion", label: "Motion", value: v.motion ? (v.motion.value ? "Motion detected" : "No motion") : "—", at: v.motion?.ts, hot: v.motion?.value },
    { icon: "bulb", label: "Smart light", value: v.light ? (v.light.value ? "On" : "Off") : "—", at: v.light?.ts, lit: v.light?.value },
  ];
  return (
    <Card title="Virtual Smart Home" sub={home?.transport === "serial"
      ? "A Wokwi-simulated ESP32 with real sensor readings. It talks over a serial link; Edge Watch's bridge publishes its readings over MQTT through the monitored hub."
      : "A Wokwi-simulated ESP32 with real sensor readings, sent over MQTT through the hub Edge Watch monitors."} className={`home-card ${live ? "" : "home-idle"}`}
      actions={<Pill tone={tone}>{live && <span className="live-dot" />}{linkText}</Pill>}>
      {link === "broker_down" ? <p className="dim">The smart-home hub is not running. Start it with <code>.\scripts\start-wokwi-home.ps1</code>, then start the simulator in VS Code.</p>
        : link === "waiting" ? <p className="dim">The hub is ready on port {home?.port}. Start the Wokwi simulator in VS Code (F1 → “Wokwi: Start Simulator”) and the readings appear here{home?.transport === "serial" ? " through the serial bridge" : ""}.</p> : null}
      {home?.monitored_port != null && home.port !== home.monitored_port && <p className="warn">The smart-home hub uses port {home.port}, but Edge Watch monitors port {home.monitored_port}: its traffic is not being analysed.</p>}
      <div className="home-tiles">
        {tiles.map((t) => (
          <div key={t.label} className={`home-tile ${t.hot ? "tile-hot" : ""} ${t.lit ? "tile-lit" : ""}`}>
            <span className="metric-icon"><Icon name={t.icon} /></span>
            <span className="metric-label">{t.label}</span>
            <b>{t.value}</b>
            <span className="metric-sub">{t.at ? `reported ${ago(t.at, now)}` : "no reading yet"}</span>
            {t.label === "Smart light" && home?.running && <button className="btn btn-sm" onClick={toggle} disabled={pending !== null || link !== "online"}>{pending !== null ? "Waiting for the light…" : v.light?.value ? "Turn off" : "Turn on"}</button>}
          </div>
        ))}
      </div>
      {error && <p className="warn" role="status">{error}</p>}
      <p className="note dim">Values are the device's own messages, checked for valid ranges. The light changes only when the ESP32 reports it did. Edge Watch's detector does not read these values; it analyses the traffic pattern.</p>
    </Card>
  );
}
