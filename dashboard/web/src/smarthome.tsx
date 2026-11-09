// Smart Home: build a home on a floor plan, run it, and see what Edge Watch makes of its traffic.
// Every state shown on a device comes from the IDS's own output or the Wokwi ESP32's own messages; nothing is generated here.
import { useEffect, useMemo, useRef, useState } from "react";
import { deviceName } from "./alerts";
import { ATTACKER, addDevice, canBeWokwi, DeviceType, H, HUB, linkSources, look, MAX_DEVICES, place, PlacedDevice, RoomId, ROOMS, sampleHome, summary, TYPES, W } from "./devices";
import { DeviceReport, HomeCard, homeLink, Home, useHome } from "./home";
import { ActivityChart, kindOf, nodesFromWindows, RecentIncidents, StatusSummary } from "./overview";
import { AlertEvent, Device, devicesOf, scenarioText, State } from "./store";
import { ago, Card, detail, fmt, Icon, Pill, send, SvgIcon, Tone, useNow } from "./ui";
import { Health, json } from "./useStream";

export const HARDWARE_NOTE = "This project is simulation-based, but the same MQTT communication flow, smart-device behaviour, monitoring pipeline and attack-detection logic could be applied to a hardware-based IoT deployment. The simulation reproduces the operational behaviour without requiring physical hardware. It has not been validated on physical devices, and it does not model radio, power or hardware timing.";

// Layout ------------------------------------------------------------------------------------------------------------------------------
export function useLayout() {
  const [devices, setDevicesState] = useState<PlacedDevice[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [save, setSave] = useState<"saved" | "saving" | "error" | "new">("new");
  const timer = useRef<number>();
  useEffect(() => { json<{ devices: PlacedDevice[]; saved: boolean }>("/api/home/layout").then((l) => { if (l) { setDevicesState(l.devices); setSave(l.saved ? "saved" : "new"); } setLoaded(true); }); }, []);
  const setDevices = (next: PlacedDevice[]) => {
    setDevicesState(next);
    setSave("saving");
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(async () => {
      try {
        const r = await fetch("/api/home/layout", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ devices: next }) });
        setSave(r.ok ? "saved" : "error");
      } catch { setSave("error"); }
    }, 400);
  };
  return { devices, setDevices, loaded, save };
}

// Live status -------------------------------------------------------------------------------------------------------------------------
export type LiveState = "alert" | "suspicious" | "normal" | "quiet" | "idle" | "offline";
export interface Live { state: LiveState; key: string | null; msgs: number | null; alerts: AlertEvent[]; reading: string | null; note: string; device?: DeviceReport; classes: string[]; icon: string | null }
const STATE_TONE: Record<LiveState, Tone> = { alert: "bad", suspicious: "warn", normal: "ok", quiet: "info", idle: "muted", offline: "muted" };
const STATE_TEXT: Record<LiveState, string> = { alert: "Alert", suspicious: "Suspicious", normal: "Normal", quiet: "Quiet", idle: "Not running", offline: "Offline" };

/** Tile border: Edge Watch's verdict on the device's traffic. Tile text and look: the device's own reported state. */
export function useLive(state: State, layout: PlacedDevice[], home: Home | null, now: number): Map<string, Live> {
  return useMemo(() => {
    const nodes = new Map((state.nodes.length ? state.nodes : nodesFromWindows(state.windows)).map((n) => [n.source_key, n]));
    const labels = devicesOf(state), links = linkSources(labels);
    const wokwiKey = Object.entries(labels).filter(([, v]) => v === "wokwi_serial" || v === "wokwi_esp32").map(([k]) => k).find((k) => nodes.get(k) && !nodes.get(k)!.silent) ?? null;
    const link = homeLink(home), v = home?.values ?? {};
    const out = new Map<string, Live>();
    for (const d of layout) {
      const key = d.source === "wokwi" ? wokwiKey : links.get(d.id) ?? null;
      const node = key ? nodes.get(key) : undefined;
      const alerts = key ? state.alerts.filter((a) => a.source_key === key) : [];
      const recent = alerts.some((a) => now - a.last_window_ns / 1e9 < 120);
      let s: LiveState = node && !node.silent ? (kindOf(node) as LiveState) : "idle", reading: string | null = null, note: string, device: DeviceReport | undefined;
      let classes: string[] = [], icon: string | null = null;
      if (d.source === "wokwi") {
        if (link !== "online") s = link === "absent" || link === "broker_down" ? "idle" : "offline";
        else if (s === "idle") s = "normal"; // readings are arriving even if the IDS has not yet closed a window for the bridge
        const kind = TYPES[d.type].wokwi;
        const r = kind === "climate" ? v.temperature : kind === "motion" ? v.motion : v.light;
        const text = kind === "climate" && v.temperature ? `${v.temperature.value.toFixed(1)} °C${v.humidity ? ` · ${v.humidity.value.toFixed(0)} %` : ""}`
          : kind === "motion" && v.motion ? (v.motion.value ? "Motion detected" : "No motion") : kind === "light" && v.light ? (v.light.value ? "On" : "Off") : null;
        reading = link === "online" ? text : null; // a stale reading is never shown as the current one
        note = link === "online" ? "Live readings from the Wokwi ESP32" : link === "waiting" ? "Hub ready; start the Wokwi simulator" : link === "absent" || link === "broker_down" ? "Wokwi hub not running" : "Wokwi ESP32 not reporting";
        if (link !== "online" && text && r) note += `. Last reported ${text}, ${ago(r.ts, home?.now ?? now)}`;
        if (link === "online" && kind === "light" && v.light?.value) classes = ["dv-on"];
        if (link === "online" && kind === "motion" && v.motion?.value) classes = ["dv-motion"];
      } else {
        device = home?.devices?.[d.id];
        const st = device?.state;
        if (!home?.running) { s = "idle"; note = "The smart-home hub is not running"; }
        else if (!st) { s = "idle"; note = "Starting: waiting for the device's first report"; }
        else if (device!.status !== "online") { s = "offline"; note = `Offline. Last reported ${summary(d.type, st)}, ${ago(device!.ts ?? 0, home?.now ?? now)}`; }
        else {
          s = node ? ((node.state ?? "normal") as LiveState) : "quiet"; // an online device keeps the verdict on its last analysed traffic
          note = node ? "Edge Watch is analysing this device's MQTT traffic" : "Connected; Edge Watch has not analysed its traffic yet";
          reading = summary(d.type, st);
          ({ classes, icon } = look(d.type, st));
        }
      }
      if (recent) s = "alert";
      out.set(d.id, { state: s, key, msgs: node && !node.silent ? node.msgs_per_s : null, alerts, reading, note, device, classes, icon });
    }
    return out;
  }, [state.nodes, state.windows, state.markers, state.alerts, layout, home, now]);
}

/** The attacker drawn outside the house: a scheduled attack that has started, with the IDS's state for its source. */
export function useAttacker(state: State, now: number) {
  return useMemo(() => {
    const m = [...state.markers].reverse().find((x) => x.marker === "scheduled_attack" && x.start_ns! / 1e9 <= now && x.end_ns! / 1e9 + 20 > now);
    if (!m) return null;
    const node = (state.nodes.length ? state.nodes : nodesFromWindows(state.windows)).find((n) => n.source_key === m.source_key);
    const alerted = state.alerts.some((a) => a.source_key === m.source_key && a.start_ns >= m.start_ns! - 5e9);
    return { family: m.family ?? "", key: m.source_key!, state: alerted ? "alert" : node && !node.silent ? kindOf(node) : "normal", msgs: node?.msgs_per_s ?? 0, active: m.end_ns! / 1e9 > now };
  }, [state.markers, state.nodes, state.windows, state.alerts, now]);
}

// Floor plan --------------------------------------------------------------------------------------------------------------------------
type Attacker = ReturnType<typeof useAttacker>;
const pulses = (msgs: number | null) => (msgs && msgs > 0 ? Math.min(3, 1 + Math.floor(Math.log10(msgs + 1))) : 0);

export function FloorPlan({ devices, live, attacker, selected, onSelect, onChange, svgRef, editable }: {
  devices: PlacedDevice[]; live: Map<string, Live>; attacker: Attacker; selected?: string | null; onSelect?: (id: string | null) => void;
  onChange?: (d: PlacedDevice[]) => void; svgRef?: React.RefObject<SVGSVGElement>; editable?: boolean;
}) {
  const own = useRef<SVGSVGElement>(null), ref = svgRef ?? own;
  const [drag, setDrag] = useState<{ id: string; dx: number; dy: number; x: number; y: number; moved: boolean } | null>(null);
  const toSvg = (cx: number, cy: number) => { const p = ref.current!.createSVGPoint(); p.x = cx; p.y = cy; return p.matrixTransform(ref.current!.getScreenCTM()!.inverse()); };
  const commit = (id: string, x: number, y: number) => {
    const spot = place(devices, x, y, id);
    if (spot) onChange?.(devices.map((d) => (d.id === id ? { ...d, ...spot } : d)));
  };
  const shown = (d: PlacedDevice) => (drag?.id === d.id ? { ...d, x: drag.x, y: drag.y } : d);
  const anyAlert = devices.some((d) => live.get(d.id)?.state === "alert") || attacker?.state === "alert";
  return (
    <svg ref={ref} viewBox={`0 0 ${W} ${H}`} className={`floor ${editable ? "floor-edit" : ""}`} role="application" aria-label="Smart home floor plan"
      onPointerMove={(e) => { if (drag) { const p = toSvg(e.clientX, e.clientY); setDrag({ ...drag, x: p.x - drag.dx, y: p.y - drag.dy, moved: drag.moved || Math.hypot(p.x - drag.dx - drag.x, p.y - drag.dy - drag.y) > 2 }); } }}
      onPointerUp={() => { if (drag) { if (drag.moved) commit(drag.id, drag.x, drag.y); else onSelect?.(drag.id); setDrag(null); } }}
      onPointerDown={(e) => { if (e.target === e.currentTarget || (e.target as Element).classList.contains("room")) onSelect?.(null); }}>
      <defs>
        <pattern id="tiles" width="20" height="20" patternUnits="userSpaceOnUse"><path d="M20 0H0V20" fill="none" className="tile" /></pattern>
      </defs>
      <rect x={20} y={20} width={930} height={600} rx={18} className="house" />
      {ROOMS.map((r) => <g key={r.id}><rect x={r.x} y={r.y} width={r.w} height={r.h} className="room" /><text x={r.x + 14} y={r.y + 24} className="room-name">{r.name}</text></g>)}
      <text x={ATTACKER.x} y={44} textAnchor="middle" className="outside">Outside the home</text>
      {devices.map((raw) => {
        const d = shown(raw), l = live.get(d.id), path = `M${d.x},${d.y} L${HUB.x},${HUB.y}`;
        return (
          <g key={d.id}>
            <path d={path} className={`wire wire-${l?.state ?? "idle"}`} />
            {Array.from({ length: pulses(l?.msgs ?? null) }, (_, j) => <circle key={j} r={3} className={`particle p-${l?.state}`}><animateMotion dur={`${Math.max(0.9, 2.6 - Math.log10((l?.msgs ?? 0) + 1))}s`} begin={`${j * 0.8}s`} repeatCount="indefinite" path={path} /></circle>)}
          </g>
        );
      })}
      {attacker && (
        <g className={`attacker attacker-${attacker.state}`}>
          <path d={`M${ATTACKER.x},${ATTACKER.y} L${HUB.x},${HUB.y}`} className="wire wire-attack" />
          {attacker.active && Array.from({ length: Math.max(1, pulses(attacker.msgs)) }, (_, j) => <circle key={j} r={3.5} className="particle p-alert"><animateMotion dur="1.1s" begin={`${j * 0.35}s`} repeatCount="indefinite" path={`M${ATTACKER.x},${ATTACKER.y} L${HUB.x},${HUB.y}`} /></circle>)}
          <g transform={`translate(${ATTACKER.x} ${ATTACKER.y})`}>
            {attacker.state === "alert" && <circle r={34} className="ripple" />}
            <circle r={32} className="attacker-core" />
            <g className="attacker-icon"><SvgIcon name="attack" size={26} /></g>
            <text y={52} textAnchor="middle" className="attacker-label">Lab attacker</text>
            <text y={68} textAnchor="middle" className="attacker-sub">{scenarioText(attacker.family).name}</text>
          </g>
        </g>
      )}
      <g transform={`translate(${HUB.x} ${HUB.y})`} className={`hub-node ${attacker?.active ? "hub-under-attack" : ""}`}>
        <circle r={40} className="hub-ring" />
        <circle r={30} className="hub-core" />
        <g className="hub-icon"><SvgIcon name="hub" size={24} /></g>
        <text y={-44} textAnchor="middle" className="hub-label">Smart-home hub</text>
        <g transform="translate(54 34)" className="engine">
          <line x1={-30} y1={-18} x2={-14} y2={-8} className="tap" />
          <circle r={16} className={`engine-core ${anyAlert ? "engine-alert" : ""}`} />
          <g className="engine-icon"><SvgIcon name="shield" size={16} /></g>
          <text x={22} y={5} className="engine-label">Edge Watch</text>
        </g>
      </g>
      {devices.map((raw) => {
        const d = shown(raw), l = live.get(d.id), t = TYPES[d.type], st = l?.state ?? "idle", sel = selected === d.id;
        return (
          <g key={d.id} transform={`translate(${d.x} ${d.y})`} className={`fp-device st-${st} ${(l?.classes ?? []).join(" ")} ${sel ? "fp-sel" : ""} ${drag?.id === d.id ? "fp-drag" : ""}`} tabIndex={0} role="button"
            aria-label={`${d.name}, ${t.label} in ${ROOMS.find((r) => r.id === d.room)?.name}, ${STATE_TEXT[st]}${l?.reading ? `, ${l.reading}` : ""}`}
            onPointerDown={(e) => { e.stopPropagation(); if (!editable) { onSelect?.(d.id); return; } const p = toSvg(e.clientX, e.clientY); (e.currentTarget.ownerSVGElement as SVGSVGElement).setPointerCapture(e.pointerId); setDrag({ id: d.id, dx: p.x - d.x, dy: p.y - d.y, x: d.x, y: d.y, moved: false }); }}
            onKeyDown={(e) => {
              const step = { ArrowLeft: [-20, 0], ArrowRight: [20, 0], ArrowUp: [0, -20], ArrowDown: [0, 20] }[e.key];
              if (step && editable) { e.preventDefault(); commit(d.id, d.x + step[0], d.y + step[1]); }
              else if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onSelect?.(d.id); }
              else if ((e.key === "Delete" || e.key === "Backspace") && editable) { e.preventDefault(); onChange?.(devices.filter((x) => x.id !== d.id)); onSelect?.(null); }
            }}>
            {st === "alert" && <circle r={36} className="ripple" key={l?.alerts.length} />}
            {l?.classes.includes("dv-alarm") && <><circle r={40} className="safety-ring" /><text y={-42} textAnchor="middle" className="safety-tag">SAFETY ALARM</text></>}
            <rect x={-30} y={-30} width={60} height={60} rx={16} className="fp-tile" />
            <g className="fp-icon"><SvgIcon name={l?.icon ?? t.icon} size={26} /></g>
            {l?.classes.includes("dv-rec") && <circle cx={20} cy={20} r={4} className="rec-dot" />}
            {d.source === "wokwi" && <g transform="translate(-30 -30)"><rect width={22} height={16} rx={5} className="fp-wokwi" /><text x={11} y={11.5} textAnchor="middle" className="fp-wokwi-text">W</text></g>}
            {(l?.alerts.length ?? 0) > 0 && <g transform="translate(28 -28)"><circle r={9} className="badge-dot" /><text y={3.5} textAnchor="middle" className="badge-num">{l!.alerts.length > 9 ? "9+" : l!.alerts.length}</text></g>}
            <text y={50} textAnchor="middle" className="fp-name">{d.name.length > 20 ? `${d.name.slice(0, 19)}…` : d.name}</text>
            <text y={66} textAnchor="middle" className="fp-state">{l?.reading ?? STATE_TEXT[st]}</text>
          </g>
        );
      })}
    </svg>
  );
}

// Page ----------------------------------------------------------------------------------------------------------------------------------
export type LayoutState = ReturnType<typeof useLayout>;
export function SmartHomePage({ state, health, connected, devices: directory, layout, onOpen, go }: { state: State; health: Health | null; connected: boolean; devices: Map<string, Device>; layout: LayoutState; onOpen: (a: AlertEvent) => void; go: (r: string) => void }) {
  const { devices, setDevices, loaded, save } = layout;
  const home = useHome();
  const now = useNow(2000);
  const live = useLive(state, devices, home, now);
  const alarms = devices.filter((d) => live.get(d.id)?.classes.includes("dv-alarm"));
  const attacker = useAttacker(state, now);
  const [selected, setSelected] = useState<string | null>(null);
  const [ghost, setGhost] = useState<{ type: DeviceType; x: number; y: number } | null>(null);
  const svg = useRef<SVGSVGElement>(null);
  const wokwiReady = homeLink(home) !== "absent";
  const sel = devices.find((d) => d.id === selected) ?? null;
  const unplaced = useMemo(() => {
    const linked = new Set([...live.values()].map((l) => l.key).filter(Boolean));
    const wokwiPlaced = devices.some((d) => d.source === "wokwi");
    const active = new Set(state.nodes.filter((n) => !n.silent).map((n) => n.source_key)); // only what is talking now
    return state.order.filter((k) => {
      const p = directory.get(k);
      return active.has(k) && !linked.has(k) && p?.kind === "profile" && !p.profile?.startsWith("edgewatch") && !(wokwiPlaced && p.profile?.startsWith("wokwi"));
    }).map((k) => directory.get(k)!);
  }, [state.order, live, directory]);

  // Palette drag: pointer events, so it works with a mouse, a pen and touch, and drops are converted into floor-plan units.
  useEffect(() => {
    if (!ghost) return;
    const move = (e: PointerEvent) => setGhost((g) => g && { ...g, x: e.clientX, y: e.clientY });
    const up = (e: PointerEvent) => {
      const el = svg.current;
      if (el) {
        const b = el.getBoundingClientRect();
        if (e.clientX >= b.left && e.clientX <= b.right && e.clientY >= b.top && e.clientY <= b.bottom) {
          const p = el.createSVGPoint(); p.x = e.clientX; p.y = e.clientY;
          const q = p.matrixTransform(el.getScreenCTM()!.inverse());
          const next = addDevice(devices, ghost.type, q.x, q.y);
          if (next !== devices) { setDevices(next); setSelected(next[next.length - 1].id); }
        }
      }
      setGhost(null);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up, { once: true });
    return () => { window.removeEventListener("pointermove", move); window.removeEventListener("pointerup", up); };
  }, [ghost?.type, devices]);

  const addInRoom = (type: DeviceType, room: RoomId = (sel?.room ?? "living")) => {
    const r = ROOMS.find((x) => x.id === room)!;
    const next = addDevice(devices, type, r.x + r.w / 2, r.y + r.h / 2, room);
    if (next !== devices) { setDevices(next); setSelected(next[next.length - 1].id); }
  };
  const update = (patch: Partial<PlacedDevice>) => sel && setDevices(devices.map((d) => (d.id === sel.id ? { ...d, ...patch } : d)));

  return (
    <div className="page">
      <StatusSummary state={state} health={health} connected={connected} devices={directory} onOpen={onOpen} go={go} />
      {alarms.length > 0 && (
        <div className="safety-banner" role="alert"><Icon name="flame" size={22} />
          <div><b>Smoke alarm: {alarms.map((d) => `${d.name} (${ROOMS.find((r) => r.id === d.room)!.name})`).join(", ")}</b>
            <p>A device safety alarm from a simulated smoke sensor, not a security alert from Edge Watch. Reset it from the sensor's panel.</p></div>
        </div>
      )}
      <div className="sh-grid">
        <aside className="card palette" aria-label="Device palette">
          <h2>Add devices</h2>
          <p className="card-sub">Drag onto a room, or press + to add to {ROOMS.find((r) => r.id === (sel?.room ?? "living"))!.name.toLowerCase()}.</p>
          <ul>
            {(Object.keys(TYPES) as DeviceType[]).map((t) => (
              <li key={t} className="pal-item" onPointerDown={(e) => { if ((e.target as Element).closest("button")) return; e.preventDefault(); setGhost({ type: t, x: e.clientX, y: e.clientY }); }}>
                <span className="pal-icon"><Icon name={TYPES[t].icon} size={20} /></span>
                <span className="pal-name">{TYPES[t].label}{TYPES[t].wokwi && <small>Wokwi-capable</small>}</span>
                <button className="icon-btn icon-sm" aria-label={`Add a ${TYPES[t].label.toLowerCase()}`} onClick={() => addInRoom(t)} disabled={devices.length >= MAX_DEVICES}><Icon name="plus" size={16} /></button>
              </li>
            ))}
          </ul>
          <p className="note dim">{devices.length} of {MAX_DEVICES} devices · {save === "saved" ? "Layout saved" : save === "saving" ? "Saving…" : save === "error" ? "Not saved: Edge Watch refused or is unreachable" : "Not saved yet"}</p>
        </aside>
        <Card title="Your smart home" sub="Each device connects to the hub; Edge Watch watches a passive copy of that traffic." className="floor-card"
          actions={<div className="legend-row"><span className="lg lg-normal">Normal</span><span className="lg lg-suspicious">Suspicious</span><span className="lg lg-alert">Alert</span><span className="lg lg-quiet">Quiet</span><span className="lg lg-silent">Off / not running</span><span className="lg lg-safety">Safety alarm</span><span className="lg lg-wokwi">W = Wokwi device</span></div>}>
          <div className="floor-wrap">
            <FloorPlan devices={devices} live={live} attacker={attacker} selected={selected} onSelect={setSelected} onChange={setDevices} svgRef={svg} editable />
            {loaded && !devices.length && (
              <div className="onboard">
                <Icon name="home" size={30} />
                <b>Build your smart home</b>
                <p>Drag devices from the left into the rooms, or start from a sample home. Then run the home and try an attack.</p>
                <div className="row-actions"><button className="btn btn-primary" onClick={() => setDevices(sampleHome(wokwiReady))}>Start with a sample home</button></div>
                {wokwiReady && <p className="dim">The sample uses your Wokwi ESP32 for the temperature sensor, motion sensor and light.</p>}
              </div>
            )}
          </div>
          {unplaced.length > 0 && (
            <div className="unplaced"><span className="dim">Also seen on the network, not on your plan:</span>{unplaced.slice(0, 16).map((d) => <span key={d.key} className="chip-dev"><Icon name={d.icon} size={14} /><span className="node-dev">{d.name}</span></span>)}{unplaced.length > 16 && <span className="dim">+{unplaced.length - 16} more</span>}</div>
          )}
        </Card>
        <aside className="card inspector" aria-label="Device details">
          {sel ? <Inspector key={sel.id} device={sel} devices={devices} live={live.get(sel.id)} home={home} directory={directory} onOpen={onOpen} update={update}
            remove={() => { setDevices(devices.filter((d) => d.id !== sel.id)); setSelected(null); }} close={() => setSelected(null)} />
            : <HomePanel devices={devices} home={home} live={live} />}
        </aside>
      </div>
      <div className="sh-lower">
        <RecentIncidents state={state} devices={directory} onOpen={onOpen} go={go} />
        <ActivityChart state={state} />
      </div>
      {ghost && <div className="drag-ghost" style={{ left: ghost.x, top: ghost.y }}><Icon name={TYPES[ghost.type].icon} size={24} /><span>{TYPES[ghost.type].label}</span></div>}
    </div>
  );
}

function Inspector({ device: d, devices, live: l, home, directory, onOpen, update, remove, close }: {
  device: PlacedDevice; devices: PlacedDevice[]; live?: Live; home: Home | null; directory: Map<string, Device>; onOpen: (a: AlertEvent) => void;
  update: (p: Partial<PlacedDevice>) => void; remove: () => void; close: () => void;
}) {
  const t = TYPES[d.type], wokwiOk = canBeWokwi(devices, d.type, d.id);
  const [pending, setPending] = useState<boolean | null>(null);
  const [error, setError] = useState<string | null>(null);
  const lightOn = home?.values?.light?.value;
  useEffect(() => { if (pending !== null && lightOn === pending) setPending(null); }, [lightOn, pending]);
  return (
    <div className="insp">
      <header className="insp-head"><span className="pal-icon"><Icon name={t.icon} size={22} /></span><div><h2>{d.name}</h2><p className="card-sub">{t.label}</p></div><button className="icon-btn icon-sm" onClick={close} aria-label="Close details"><Icon name="x" size={16} /></button></header>
      <div className="insp-status">
        <Pill tone={STATE_TONE[l?.state ?? "idle"]}>{STATE_TEXT[l?.state ?? "idle"]}</Pill>
        {l?.reading && <b className="insp-reading">{l.reading}</b>}
        {l?.msgs != null && !l.reading && <span className="dim">{fmt(l.msgs)} messages/s</span>}
        <p className="dim">{l?.note}</p>
        {d.source === "wokwi" && d.type === "light" && homeLink(home) === "online" && (
          <button className="btn btn-sm" disabled={pending !== null} onClick={async () => { const on = !lightOn; setPending(on); const r = await send("/api/home/light", { on }); if (!r.ok) { setPending(null); setError(`Refused (${r.status}): ${detail(r.data)}`); } }}>
            {pending !== null ? "Waiting for the light…" : lightOn ? "Turn off" : "Turn on"}
          </button>
        )}
        {error && <p className="warn">{error}</p>}
        {d.source === "software" && l?.device?.state && <dl className="mini-facts"><div><dt>Connection</dt><dd className="dd-sm">{l.device.status === "online" ? "Online" : "Offline"}</dd></div><div><dt>Last update</dt><dd className="dd-sm">{l.device.ts ? ago(l.device.ts, home?.now ?? Date.now() / 1000) : "—"}</dd></div></dl>}
        {d.source === "software" && home?.running && <DeviceControls key={`${d.id}-${d.type}`} device={d} report={l?.device} />}
        {d.source === "wokwi" && d.type === "motion" && <p className="dim">Click the PIR sensor in the Wokwi diagram to simulate motion.</p>}
        {d.source === "wokwi" && d.type === "climate" && <p className="dim">Click the DHT22 in the Wokwi diagram to change its temperature and humidity.</p>}
        {(l?.alerts.length ?? 0) > 0 && <button className="btn btn-sm btn-danger" onClick={() => onOpen([...l!.alerts].sort((a, b) => b.start_ns - a.start_ns)[0])}>{l!.alerts.length} alert{l!.alerts.length > 1 ? "s" : ""}: see the latest</button>}
      </div>
      <label className="field-sm">Name<input value={d.name} maxLength={40} onChange={(e) => update({ name: e.target.value || t.label })} /></label>
      <label className="field-sm">Type<select value={d.type} onChange={(e) => { const type = e.target.value as DeviceType; update({ type, source: d.source === "wokwi" && canBeWokwi(devices, type, d.id) ? "wokwi" : "software" }); }}>{(Object.keys(TYPES) as DeviceType[]).map((x) => <option key={x} value={x}>{TYPES[x].label}</option>)}</select></label>
      <label className="field-sm">Room<select value={d.room} onChange={(e) => { const room = e.target.value as RoomId, r = ROOMS.find((x) => x.id === room)!; const spot = place(devices, r.x + r.w / 2, r.y + r.h / 2, d.id, room); if (spot) update(spot); }}>{ROOMS.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}</select></label>
      <fieldset className="plain backing">
        <legend>Simulated by</legend>
        <label className="check"><input type="radio" checked={d.source === "software"} onChange={() => update({ source: "software" })} />Software device<small>Runs in Edge Watch's device host as its own MQTT client. Its values come from a simple simulation, not a sensor.</small></label>
        <label className={`check ${wokwiOk ? "" : "disabled"}`}><input type="radio" disabled={!wokwiOk} checked={d.source === "wokwi"} onChange={() => update({ source: "wokwi" })} />Wokwi ESP32<small>{t.wokwi ? (wokwiOk ? "Real readings from the virtual board's sensor, via the serial bridge." : "The board's sensor is already used by another device.") : "The Wokwi board has no such sensor."}</small></label>
      </fieldset>
      <p className="note dim">{t.behaviour} {l?.key && <>Source: {deviceName(directory, l.key)}.</>}</p>
      <button className="btn btn-danger btn-sm" onClick={remove}><Icon name="trash" size={14} />Remove device</button>
    </div>
  );
}

const APPLIANCES: [string, number][] = [["Lamp", 60], ["TV", 120], ["Fridge", 150], ["Heater", 1500], ["Kettle", 2000]];

/** Per-type controls. A command counts as done only when the device's next state echoes its cmd_id. */
function DeviceControls({ device: d, report }: { device: PlacedDevice; report?: DeviceReport }) {
  const [pending, setPending] = useState<{ cmd: string; at: number } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [room, setRoom] = useState<{ t: number; h: number } | null>(null);
  const now = useNow(1000);
  const s = report?.state ?? {};
  useEffect(() => { if (pending && s.ack === pending.cmd) setPending(null); }, [s.ack, pending]);
  useEffect(() => { if (pending && now - pending.at > 8) { setPending(null); setError("No confirmation from the device within 8 s; its state was not changed on the dashboard."); } }, [now, pending]);
  const online = report?.status === "online", busy = !!pending || !online;
  async function go(body: object) {
    setError(null);
    const r = await send(`/api/home/devices/${d.id}/command`, body);
    if (r.ok) setPending({ cmd: r.data.cmd_id, at: Date.now() / 1000 });
    else setError(`Refused (${r.status}): ${detail(r.data)}`);
  }
  const B = ({ label, body, on, danger }: { label: string; body: object; on?: boolean; danger?: boolean }) =>
    <button className={`btn btn-sm ${on ? "btn-on-state" : ""} ${danger ? "btn-danger" : ""}`} aria-pressed={on} disabled={busy} onClick={() => go(body)}>{label}</button>;
  const events = (report?.events ?? []).slice(0, 4);
  return (
    <div className="controls">
      {d.type === "light" && <div className="row-actions"><B label="On" body={{ on: true }} on={s.on} /><B label="Off" body={{ on: false }} on={!s.on} /></div>}
      {d.type === "motion" && <div className="row-actions"><B label="Trigger motion" body={{ trigger: true }} />
        <select aria-label="Clear after" value={s.clear_after_s} disabled={busy} onChange={(e) => go({ clear_after_s: +e.target.value })}>{[5, 10, 30, 60].map((n) => <option key={n} value={n}>clears after {n} s</option>)}</select></div>}
      {d.type === "climate" && <div className="ctl-grid">
        <label>Room temperature {room?.t ?? s.room_temperature} °C<input type="range" min={10} max={35} step={0.5} value={room?.t ?? s.room_temperature} onChange={(e) => setRoom({ t: +e.target.value, h: room?.h ?? s.room_humidity })} /></label>
        <label>Room humidity {room?.h ?? s.room_humidity} %<input type="range" min={20} max={90} step={1} value={room?.h ?? s.room_humidity} onChange={(e) => setRoom({ t: room?.t ?? s.room_temperature, h: +e.target.value })} /></label>
        <button className="btn btn-sm" disabled={busy || !room} onClick={() => { go({ room_temperature: room!.t, room_humidity: room!.h }); setRoom(null); }}>Apply to the room</button>
        <p className="dim">The sensor's reading moves towards the room's conditions over a few seconds.</p></div>}
      {d.type === "door" && <div className="row-actions"><B label="Open" body={{ open: true }} on={s.open} /><B label="Close" body={{ open: false }} on={!s.open} /></div>}
      {d.type === "door" && s.changed && <p className="dim">Last change {ago(s.changed, now)}</p>}
      {d.type === "lock" && <><div className="row-actions"><B label="Lock" body={{ locked: true }} on={s.locked} /><B label="Unlock" body={{ locked: false }} on={!s.locked} /></div>
        <div className="row-actions"><span className="dim">Simulated keypad:</span><B label="Correct code" body={{ attempt: "correct" }} /><B label="Wrong code" body={{ attempt: "wrong" }} /></div>
        <p className="dim">{s.failed_attempts} failed attempt{s.failed_attempts === 1 ? "" : "s"} since the last success. The keypad is simulated; no real authentication is implemented, and these attempts are not Edge Watch security alerts.</p></>}
      {d.type === "camera" && <div className="row-actions"><B label={s.monitoring ? "Pause monitoring" : "Start monitoring"} body={{ monitoring: !s.monitoring }} />
        <button className="btn btn-sm" disabled={busy || !s.monitoring} onClick={() => go({ simulate_motion: true })}>Simulate motion</button></div>}
      {d.type === "camera" && <p className="dim">{s.motion_events} motion event{s.motion_events === 1 ? "" : "s"}{s.last_motion ? `, last ${ago(s.last_motion, now)}` : ""}. Event notifications only; there is no video.</p>}
      {d.type === "plug" && <><div className="row-actions"><B label="On" body={{ on: true }} on={s.on} /><B label="Off" body={{ on: false }} on={!s.on} />
        <select aria-label="Appliance" value={s.appliance_w} disabled={busy} onChange={(e) => go({ appliance_w: +e.target.value })}>{APPLIANCES.map(([n, w]) => <option key={n} value={w}>{n} ({w} W)</option>)}{!APPLIANCES.some(([, w]) => w === s.appliance_w) && <option value={s.appliance_w}>{s.appliance_w} W</option>}</select></div>
        <p className="dim">Simulated: {Number(s.power_w).toFixed(1)} W now, {Number(s.energy_wh).toFixed(2)} Wh so far.</p></>}
      {d.type === "thermostat" && <><div className="row-actions stepper"><button className="icon-btn icon-sm" aria-label="Lower target" disabled={busy || s.target <= 10} onClick={() => go({ target: s.target - 0.5 })}>−</button>
        <b className="insp-reading">{Number(s.target).toFixed(1)} °C</b><button className="icon-btn icon-sm" aria-label="Raise target" disabled={busy || s.target >= 30} onClick={() => go({ target: s.target + 0.5 })}>+</button><span className="dim">target</span></div>
        <p className="dim">Room {Number(s.current).toFixed(1)} °C, {s.mode === "idle" ? "at target" : s.mode}. A simple simulated room: 0.05 °C per second.</p></>}
      {d.type === "smoke" && <><div className="row-actions"><B label="Simulate smoke" body={{ smoke: true }} /><B label="Reset" body={{ reset: true }} />
        <select aria-label="Alarm threshold" value={s.threshold} disabled={busy} onChange={(e) => go({ threshold: +e.target.value })}>{[10, 20, 30, 50].map((n) => <option key={n} value={n}>alarm at level {n}</option>)}</select></div>
        <div className="level"><i style={{ width: `${Math.min(100, s.level)}%` }} className={s.alarm ? "level-alarm" : ""} /><span>Smoke level {Number(s.level).toFixed(0)} (simulated)</span></div>
        {s.alarm && <p className="safety-note">Safety alarm. This is a device event, not a security alert from Edge Watch.</p>}</>}
      {pending && <p className="dim" role="status">Sent; waiting for the device to confirm…</p>}
      {!online && <p className="dim">The device is offline, so it cannot take commands.</p>}
      {error && <p className="warn" role="status">{error}</p>}
      {events.length > 0 && <ul className="events">{events.map((e, i) => <li key={i}><span>{e.event}{e.result ? `: ${e.result}` : ""}</span><span className="dim">{ago(e.at, now)}</span></li>)}</ul>}
    </div>
  );
}

function HomePanel({ devices, home, live }: { devices: PlacedDevice[]; home: Home | null; live: Map<string, Live> }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const running = !!home?.running;
  const software = devices.filter((d) => d.source === "software"), wokwi = devices.length - software.length;
  const online = software.filter((d) => live.get(d.id)?.device?.status === "online").length;
  async function act(path: string) {
    setBusy(true);
    const r = await send(path);
    setError(r.ok ? null : `Refused (${r.status}): ${detail(r.data)}`);
    setBusy(false);
  }
  return (
    <div className="insp">
      <header className="insp-head"><span className="pal-icon"><Icon name="home" size={22} /></span><div><h2>Home</h2><p className="card-sub">{devices.length} devices · {software.length} software, {wokwi} Wokwi</p></div></header>
      <div className="run-box">
        <b>Smart-home hub {running ? <Pill tone="ok"><span className="live-dot" />Running</Pill> : <Pill tone="muted">Stopped</Pill>}</b>
        <p className="dim">{running ? `${online} of ${software.length} software devices online. Each is its own MQTT client; select one to control it.` : "Start the hub to bring your devices online: the message broker, one MQTT client per software device, and the Wokwi serial bridge."}</p>
        {running ? <button className="btn btn-danger btn-sm" disabled={busy} onClick={() => act("/api/home/stop")}><Icon name="stop" size={14} />Stop hub</button>
          : <button className="btn btn-primary" disabled={busy} onClick={() => act("/api/home/start")}><Icon name="play" size={16} />Start hub</button>}
        {error && <p className="warn">{error}</p>}
      </div>
      <HomeCard home={home} compact />
      <details className="more hw-note"><summary>Simulation and real hardware</summary><p className="dim">{HARDWARE_NOTE}</p></details>
    </div>
  );
}
