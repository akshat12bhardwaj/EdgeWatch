// Smart Home: a 3D home and accessible device controls, backed by reported state.
// Every state shown on a device comes from the IDS's own output or the Wokwi ESP32's own messages; nothing is generated here.
import { lazy, Suspense, useEffect, useMemo, useRef, useState } from "react";
import { deviceName } from "./alerts";
import { addDevice, canBeWokwi, canUseController, controllerHome, CONTROLLERS, Controller, DeviceType, linkSources, look, MAX_DEVICES, place, PlacedDevice, RoomId, ROOMS, sampleHome, summary, TYPES } from "./devices";
import { DeviceReport, deviceSummary, homeLink, Home, useHome } from "./home";
import { kindOf, nodesFromWindows } from "./overview";
import { Activity, AlertEvent, Device, devicesOf, State, WindowEvent } from "./store";
import { ago, clock, detail, fmt, Icon, Pill, send, Tone, useNow } from "./ui";
import { json } from "./useStream";
const Home3D = lazy(() => import("./home3d"));

// Layout ------------------------------------------------------------------------------------------------------------------------------

export function useLayout() {
  const [devices, setDevicesState] = useState<PlacedDevice[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [save, setSave] = useState<"saved" | "saving" | "error" | "new">("new");
  const timer = useRef<number>();
  const writes = useRef<Promise<void>>(Promise.resolve());
  const revision = useRef(0);
  useEffect(() => { json<{ devices: PlacedDevice[]; saved: boolean }>("/api/home/layout").then((l) => { if (l) { setDevicesState(l.devices); setSave(l.saved ? "saved" : "new"); setLoaded(true); } else setSave("error"); }); }, []);
  const setDevices = (next: PlacedDevice[]) => {
    if (!loaded) return;
    const version = ++revision.current;
    setDevicesState(next);
    setSave("saving");
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => {
      writes.current = writes.current.then(async () => {
        try {
          const r = await fetch("/api/home/layout", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ devices: next }) });
          if (version === revision.current) setSave(r.ok ? "saved" : "error");
        } catch { if (version === revision.current) setSave("error"); }
      });
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
      const controllerKey = d.controller ? Object.entries(labels).find(([, label]) => label === `wokwi_${d.controller}`)?.[0] ?? null : null;
      const key = d.controller ? controllerKey : d.source === "wokwi" ? wokwiKey : links.get(d.id) ?? null;
      const node = key ? nodes.get(key) : undefined;
      const alerts = key ? state.alerts.filter((a) => a.source_key === key) : [];
      const recent = alerts.some((a) => now - a.last_window_ns / 1e9 < 120);
      let s: LiveState = node && !node.silent ? (kindOf(node) as LiveState) : "idle", reading: string | null = null, note: string, device: DeviceReport | undefined;
      let classes: string[] = [], icon: string | null = null;
      if (d.source === "wokwi" && !d.controller) {
        if (link !== "online") s = link === "absent" || link === "broker_down" ? "idle" : "offline";
        else if (s === "idle") s = "quiet"; // readings are arriving even if the IDS has not yet closed a window for the bridge
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
        const st = device?.state?.type === d.type ? device.state : null;
        if (!home?.running) { s = "idle"; note = "The smart-home hub is not running"; }
        else if (!st) { s = "idle"; note = "Starting: waiting for the device's first report"; }
        else if (!deviceSummary(home).online_ids.includes(d.id)) { s = "offline"; note = `Offline. Last reported ${summary(d.type, st)}, ${ago(device!.ts ?? 0, home?.now ?? now)}`; }
        else {
          s = node ? ((node.state ?? "normal") as LiveState) : "quiet"; // an online device keeps the verdict on its last analysed traffic
          note = d.controller ? `${CONTROLLERS[d.controller].label} is reporting.` : node ? "Edge Watch is analysing this device's MQTT traffic" : "Connected; Edge Watch has not analysed its traffic yet";
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
    const m = [...state.markers].reverse().find((x) => x.marker === "scheduled_attack" && x.start_ns! / 1e9 <= now && x.end_ns! / 1e9 + 120 > now);
    if (!m) return null;
    const node = (state.nodes.length ? state.nodes : nodesFromWindows(state.windows)).find((n) => n.source_key === m.source_key);
    const hit = state.alerts.filter(a => a.source_key === m.source_key && a.start_ns >= m.start_ns! - 5e9 && a.start_ns <= m.end_ns! + 5e9).sort((a, b) => a.first_seen - b.first_seen)[0];
    const alerted = !!hit;
    const outcome: "processing" | "alert" | "missed" = alerted ? "alert" : now > m.end_ns! / 1e9 + 20 ? "missed" : "processing";
    const delay = hit && Number.isFinite(hit.first_seen) ? Math.max(0, hit.first_seen - m.start_ns! / 1e9) : null;
    return { outcome, delay, family: m.family ?? "", key: m.source_key!, state: alerted ? "alert" : node && !node.silent ? kindOf(node) : "normal", msgs: node?.msgs_per_s ?? 0, active: m.end_ns! / 1e9 > now };
  }, [state.markers, state.nodes, state.windows, state.alerts, now]);
}

// Accessible device management; this is a semantic list, never a graphical floor plan.

export function DeviceList({ devices, live, selected, onSelect, onChange }: {
  devices: PlacedDevice[]; live: Map<string, Live>; selected?: string | null;
  onSelect?: (id: string | null) => void; onChange?: (next: PlacedDevice[]) => void;
}) {
  const move = (e: React.KeyboardEvent<HTMLButtonElement>, d: PlacedDevice) => {
    if (!onChange) return;
    if (e.key === "Delete") { e.preventDefault(); onChange(devices.filter(x => x.id !== d.id)); onSelect?.(null); return; }
    const deltas: Record<string, [number, number]> = { ArrowLeft: [-20, 0], ArrowRight: [20, 0], ArrowUp: [0, -20], ArrowDown: [0, 20] };
    const delta = deltas[e.key]; if (!delta) return;
    e.preventDefault(); const p = place(devices, d.x + delta[0], d.y + delta[1], d.id);
    if (p) onChange(devices.map(x => x.id === d.id ? { ...x, ...p } : x));
  };
  return <section className="device-management" aria-label="Device list">
    <p className="dim">{onSelect ? "Select a device to open its controls." : "Current device status."}{onChange && " Arrow keys move a focused device; Delete removes it."}</p>
    {!devices.length ? <p>No devices yet. Use the + buttons to add one.</p> : <ul>{devices.map(d => {
      const l = live.get(d.id), room = ROOMS.find(r => r.id === d.room)?.name;
      const content = <><Icon name={TYPES[d.type].icon} size={18}/><span><b>{d.name}</b><small>{room} · {d.source === "wokwi" ? d.controller ? CONTROLLERS[d.controller].label : "Wokwi" : "Software simulation"}</small><small>{l?.reading ?? STATE_TEXT[l?.state ?? "idle"]}</small></span><Pill tone={STATE_TONE[l?.state ?? "idle"]}>{STATE_TEXT[l?.state ?? "idle"]}</Pill></>;
      return <li key={d.id}>{onSelect ? <button type="button" aria-pressed={selected === d.id} onClick={() => onSelect(d.id)} onKeyDown={e => move(e, d)}>{content}</button> : <div>{content}</div>}</li>;
    })}</ul>}
  </section>;
}

// Page ----------------------------------------------------------------------------------------------------------------------------------
export type LayoutState = ReturnType<typeof useLayout>;

export function SmartHomePage({ state, devices: directory, layout, onOpen, activity }: { state: State; devices: Map<string, Device>; layout: LayoutState; onOpen: (a: AlertEvent) => void; go?: (r: string) => void; activity: Activity }) {
  const { devices, setDevices, loaded, save } = layout;
  const home = useHome();
  const now = useNow(2000);
  const live = useLive(state, devices, home, now);
  const alarms = devices.filter((d) => live.get(d.id)?.classes.includes("dv-alarm"));
  const attacker = useAttacker(state, now);
  const [selected, setSelected] = useState<string | null>(null);
  const [ghost, setGhost] = useState<{ type: DeviceType; x: number; y: number } | null>(null);
  const sel = devices.find((d) => d.id === selected) ?? null;
  // Palette drag: pointer events, so it works with a mouse, a pen and touch, and drops are converted into floor-plan units.
  useEffect(() => {
    if (!ghost) return;
    const move = (e: PointerEvent) => setGhost((g) => g && { ...g, x: e.clientX, y: e.clientY });
    const up = () => setGhost(null);
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up, { once: true });
    return () => { window.removeEventListener("pointermove", move); window.removeEventListener("pointerup", up); };
  }, [ghost?.type, devices]);
  const addInRoom = (type: DeviceType, room: RoomId = (sel?.room ?? "living")) => {
    const r = ROOMS.find((x) => x.id === room)!;
    const next = addDevice(devices, type, r.x + r.w / 2, r.y + r.h / 2, room);
    if (next !== devices) { setDevices(next); setSelected(next[next.length - 1].id); }
  };
  const placeFromScene = (type: DeviceType, x: number, y: number) => {
    const next = addDevice(devices, type, x, y);
    if (next !== devices) { setDevices(next); setSelected(next[next.length - 1].id); }
  };
  const fallback = <DeviceList devices={devices} live={live} selected={selected} onSelect={setSelected} onChange={setDevices} />;
  const update = (patch: Partial<PlacedDevice>) => sel && setDevices(devices.map((d) => (d.id === sel.id ? { ...d, ...patch } : d)));
  return (
    <div className="page smart-home-page">
      <header className="home-heading home-heading-compact"><h1>Smart Home</h1><span className="home-mode">Local simulation</span></header>
      {alarms.length > 0 && (
        <div className="safety-banner" role="alert"><Icon name="flame" size={22} />
          <div><b>Smoke alarm: {alarms.map((d) => `${d.name} (${ROOMS.find((r) => r.id === d.room)!.name})`).join(", ")}</b>
            <p>A device safety alarm from a simulated smoke sensor, not a security alert from Edge Watch. Reset it from the sensor's panel.</p></div>
        </div>
      )}
      {!loaded && <p className="warn" role="status">The saved home could not be loaded. Reload to retry before editing devices.</p>}
      <div className="sh3">
        <section className="card sh-home" aria-label="Interactive 3D smart home">
          <div className="floor-wrap">
            <Suspense fallback={<div role="status">Preparing your home…</div>}><Home3D devices={devices} live={live} attacker={attacker} selected={selected} onSelect={setSelected} onChange={setDevices} placementType={ghost?.type} onPlace={placeFromScene} fallback={fallback} deviceList={false} /></Suspense>
            {loaded && !devices.length && (
              <div className="onboard">
                <Icon name="home" size={30} />
                <b>Build your smart home</b>
                <p>Drag devices from the right into the rooms, or start from a sample home. New devices run as software simulations.</p>
                <div className="row-actions"><button className="btn btn-primary" onClick={() => setDevices(sampleHome(false))}>Start with a sample home</button><button className="btn" onClick={() => setDevices(controllerHome())}>Use four-controller home</button></div>
              </div>
            )}
          </div>
        </section>
        <NetworkPanel state={state} home={home} devices={devices} live={live} directory={directory} activity={activity} />
        <aside className="card sh-controls" aria-label="Devices and hub">
          <HomePanel devices={devices} home={home} live={live} />
          <section className="palette" aria-label="Device palette">
            <h2>Add devices</h2>
            <p className="card-sub">Drag onto a room, or press + to add to {ROOMS.find((r) => r.id === (sel?.room ?? "living"))!.name.toLowerCase()}. New devices start as software simulations.</p>
            <ul>
              {(Object.keys(TYPES) as DeviceType[]).map((t) => (
                <li key={t} className="pal-item" onPointerDown={(e) => { if ((e.target as Element).closest("button")) return; e.preventDefault(); setGhost({ type: t, x: e.clientX, y: e.clientY }); }}>
                  <span className="pal-icon"><Icon name={TYPES[t].icon} size={18} /></span>
                  <span className="pal-name">{TYPES[t].label}</span>
                  <button className="icon-btn icon-sm" aria-label={`Add a ${TYPES[t].label.toLowerCase()}`} onClick={() => addInRoom(t)} disabled={!loaded || devices.length >= MAX_DEVICES}><Icon name="plus" size={16} /></button>
                </li>
              ))}
            </ul>
            <p className="note dim">{devices.length} of {MAX_DEVICES} devices · {save === "saved" ? "Layout saved" : save === "saving" ? "Saving…" : save === "error" ? "Not saved: Edge Watch refused or is unreachable" : "Not saved yet"}</p>
          </section>
          <section className="sh-devices"><h2>Devices</h2>{fallback}</section>
          {sel && <section className="sh-inspector"><Inspector key={sel.id} device={sel} devices={devices} live={live.get(sel.id)} home={home} directory={directory} onOpen={onOpen} update={update}
            remove={() => { setDevices(devices.filter((d) => d.id !== sel.id)); setSelected(null); }} close={() => setSelected(null)} /></section>}
        </aside>
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
  const pendingAt = useRef(0);
  const tick = useNow(1000);
  useEffect(() => { if (pending !== null && tick - pendingAt.current > 8) { setPending(null); setError("No reply from the light within 8 s. Check its connection."); } }, [tick, pending]);
  useEffect(() => { if (pending !== null && lightOn === pending) setPending(null); }, [lightOn, pending]);
  return (
    <div className="insp">
      <header className="insp-head"><span className="pal-icon"><Icon name={t.icon} size={22} /></span><div><h2>{d.name}</h2><p className="card-sub">{t.label}</p></div><button className="icon-btn icon-sm" onClick={close} aria-label="Close details"><Icon name="x" size={16} /></button></header>
      <div className="insp-status">
        <Pill tone={STATE_TONE[l?.state ?? "idle"]}>{STATE_TEXT[l?.state ?? "idle"]}</Pill>
        {l?.reading && <b className="insp-reading">{l.reading}</b>}
        {l?.msgs != null && !l.reading && <span className="dim">{fmt(l.msgs)} messages/s</span>}
        <p className="dim">{l?.note}</p>
        {d.source === "wokwi" && !d.controller && d.type === "light" && homeLink(home) === "online" && (
          <button className="btn btn-sm" disabled={pending !== null} onClick={async () => { const on = !lightOn; pendingAt.current = Date.now() / 1000; setPending(on); const r = await send("/api/home/light", { on }); if (!r.ok) { setPending(null); setError(`Refused (${r.status}): ${detail(r.data)}`); } }}>
            {pending !== null ? "Waiting for the light…" : lightOn ? "Turn off" : "Turn on"}
          </button>
        )}
        {error && <p className="warn">{error}</p>}
        {(d.source === "software" || d.controller) && l?.device?.state && <dl className="mini-facts"><div><dt>Connection</dt><dd className="dd-sm">{l.device.status === "online" ? "Online" : "Offline"}</dd></div><div><dt>Last update</dt><dd className="dd-sm">{l.device.ts ? ago(l.device.ts, home?.now ?? Date.now() / 1000) : "—"}</dd></div></dl>}
        {(d.source === "software" || d.controller) && home?.running && <DeviceControls key={`${d.id}-${d.type}`} device={d} report={l?.device} />}
        {d.source === "wokwi" && !d.controller && d.type === "motion" && <p className="dim">Click the PIR sensor in the Wokwi diagram to simulate motion.</p>}
        {d.source === "wokwi" && !d.controller && d.type === "climate" && <p className="dim">Click the DHT22 in the Wokwi diagram to change its temperature and humidity.</p>}
        {(l?.alerts.length ?? 0) > 0 && <button className="btn btn-sm btn-danger" onClick={() => onOpen([...l!.alerts].sort((a, b) => b.start_ns - a.start_ns)[0])}>{l!.alerts.length} alert{l!.alerts.length > 1 ? "s" : ""}: see the latest</button>}
      </div>
      <label className="field-sm">Name<input value={d.name} maxLength={40} onChange={(e) => update({ name: e.target.value || t.label })} /></label>
      <label className="field-sm">Type<select value={d.type} onChange={(e) => { const type = e.target.value as DeviceType; update({ type, controller: null, source: d.source === "wokwi" && canBeWokwi(devices, type, d.id) ? "wokwi" : "software" }); }}>{(Object.keys(TYPES) as DeviceType[]).map((x) => <option key={x} value={x}>{TYPES[x].label}</option>)}</select></label>
      <label className="field-sm">Room<select value={d.room} onChange={(e) => { const room = e.target.value as RoomId, r = ROOMS.find((x) => x.id === room)!; const spot = place(devices, r.x + r.w / 2, r.y + r.h / 2, d.id, room); if (spot) update(spot); }}>{ROOMS.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}</select></label>
      <fieldset className="plain backing">
        <legend>Simulated by</legend>
        <label className="check"><input type="radio" checked={d.source === "software"} onChange={() => update({ source: "software", controller: null })} />Software device<small>Local software simulation.</small></label>
        <label className={`check ${wokwiOk ? "" : "disabled"}`}><input type="radio" disabled={!wokwiOk} checked={d.source === "wokwi" && !d.controller} onChange={() => update({ source: "wokwi", controller: null })} />Wokwi ESP32<small>{t.wokwi ? (wokwiOk ? "Virtual sensor readings." : "The board's sensor is already used by another device.") : "The Wokwi board has no such sensor."}</small></label>
        {(Object.keys(CONTROLLERS) as Controller[]).filter(c => CONTROLLERS[c].types.includes(d.type)).map(c => <label className="check" key={c}><input type="radio" disabled={!canUseController(devices, d.type, c, d.id)} checked={d.source === "wokwi" && d.controller === c} onChange={() => update({ source: "wokwi", controller: c })} />{CONTROLLERS[c].label}<small>{home?.controllers?.[c]?.firmware_reporting ? "Wokwi controller reporting now. Shared by every device on this controller." : "Not reporting now: start its Wokwi simulator in VS Code."}</small></label>)}
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
  if (d.controller && ["climate", "motion", "door"].includes(d.type)) return <p className="dim">Adjust the sensor in the {CONTROLLERS[d.controller].label} Wokwi diagram. Values arrive from its firmware.</p>;
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
        {!d.controller && <div className="row-actions"><span className="dim">Simulated keypad:</span><B label="Correct code" body={{ attempt: "correct" }} /><B label="Wrong code" body={{ attempt: "wrong" }} /></div>}
        {!d.controller && <p className="dim">{s.failed_attempts} failed attempt{s.failed_attempts === 1 ? "" : "s"} since the last success. The keypad is simulated; no real authentication is implemented, and these attempts are not Edge Watch security alerts.</p>}</>}
      {d.type === "camera" && <div className="row-actions"><B label={s.monitoring ? "Pause monitoring" : "Start monitoring"} body={{ monitoring: !s.monitoring }} />
        <button className="btn btn-sm" disabled={busy || !s.monitoring} onClick={() => go({ simulate_motion: true })}>Simulate motion</button></div>}
      {d.type === "camera" && <p className="dim">{s.motion_events} motion event{s.motion_events === 1 ? "" : "s"}{s.last_motion ? `, last ${ago(s.last_motion, now)}` : ""}. Event notifications only; there is no video.</p>}
      {d.type === "plug" && <><div className="row-actions"><B label="On" body={{ on: true }} on={s.on} /><B label="Off" body={{ on: false }} on={!s.on} />
        {!d.controller && <select aria-label="Appliance" value={s.appliance_w} disabled={busy} onChange={(e) => go({ appliance_w: +e.target.value })}>{APPLIANCES.map(([n, w]) => <option key={n} value={w}>{n} ({w} W)</option>)}{!APPLIANCES.some(([, w]) => w === s.appliance_w) && <option value={s.appliance_w}>{s.appliance_w} W</option>}</select>}</div>
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
  const s = deviceSummary(home);
  async function act(path: string) {
    setBusy(true);
    const r = await send(path);
    setError(r.ok ? null : `Refused (${r.status}): ${detail(r.data)}`);
    setBusy(false);
  }
  return (
    <div className="insp">
      <header className="insp-head"><span className="pal-icon"><Icon name="home" size={22} /></span><div><h2>Home</h2><p className="card-sub">{s.total} devices · {s.software} software, {s.wokwi} Wokwi</p></div></header>
      <div className="run-box">
        <b>Smart-home hub {running ? <Pill tone="ok"><span className="live-dot" />Running</Pill> : <Pill tone="muted">Stopped</Pill>}</b>
        <p className="dim">{running ? `${s.online} of ${s.total} devices online.` : "Start the hub to connect your devices."}</p>
        {running ? <button className="btn btn-danger btn-sm" disabled={busy} onClick={() => act("/api/home/stop")}><Icon name="stop" size={14} />Stop hub</button>
          : <button className="btn btn-primary" disabled={busy} onClick={() => act("/api/home/start")}><Icon name="play" size={16} />Start hub</button>}
        {error && <p className="warn">{error}</p>}
      </div>
      {running && s.software > 0 && <p className="dim">Software devices run inside the hub and keep working when Wokwi is offline.</p>}
      {s.wokwi > 0 && <div className="backing-status"><b>Wokwi devices</b><p className="dim">{s.wokwi_online} of {s.wokwi} reporting</p>{devices.filter(d => d.source === "wokwi" && !s.online_ids.includes(d.id)).map(d => <p className="warn" key={d.id}>{d.name}: {live.get(d.id)?.state === "offline" ? "Disconnected" : "Not reporting"}</p>)}</div>}
    </div>
  );
}

// Network communication: only what the hub, the devices and the IDS actually reported. No payloads, no generated traffic.

export type NetEvent = { at: number; who: string; what: string; tone: Tone };
const READING_TYPES = new Set(["climate", "motion", "door", "smoke"]);
/** New device activity between two /api/home polls. Only configured device IDs are named; nothing is reported on the first poll. */
export function deviceActivity(prev: Record<string, DeviceReport> | undefined, next: Record<string, DeviceReport>, devices: PlacedDevice[], now: number): NetEvent[] {
  if (!prev) return [];
  const out: NetEvent[] = [];
  for (const d of devices) {
    const r = next[d.id], p = prev[d.id];
    if (!r) { if (p?.status === "online") out.push({ at: now, who: d.name, what: "no longer reported", tone: "muted" }); continue; }
    if (r.status && r.status !== p?.status) out.push({ at: now, who: d.name, what: r.status === "online" ? "connected" : "disconnected", tone: r.status === "online" ? "ok" : "muted" });
    if (r.state?.ack && r.state.ack !== p?.state?.ack) out.push({ at: r.ts ?? now, who: d.name, what: "command acknowledged", tone: "ok" });
    else if (r.ts && r.ts !== p?.ts) out.push({ at: r.ts, who: d.name, what: READING_TYPES.has(d.type) ? "reading received" : "state updated", tone: "info" });
    for (const e of r.events ?? []) if (!p?.events?.some((x) => x.at === e.at && x.event === e.event)) out.push({ at: e.at, who: d.name, what: e.event.replaceAll("_", " "), tone: "info" });
  }
  return out;
}

function NetworkPanel({ state, home, devices, live, directory, activity }: { state: State; home: Home | null; devices: PlacedDevice[]; live: Map<string, Live>; directory: Map<string, Device>; activity: Activity }) {
  const [feed, setFeed] = useState<NetEvent[]>([]);
  const prev = useRef<Record<string, DeviceReport>>();
  const seen = useRef<{ alerts: Set<string>; windows: Map<string, number> } | null>(null);
  const byKey = useMemo(() => new Map(devices.map((d) => [live.get(d.id)?.key, d.name] as const).filter(([k]) => k)), [devices, live]);
  const nameOf = (key: string) => byKey.get(key) ?? deviceName(directory, key);
  const push = (events: NetEvent[]) => events.length && setFeed((f) => [...events, ...f].sort((a, b) => b.at - a.at).slice(0, 8));
  useEffect(() => {
    if (!home) return;
    const next = home.running ? home.devices ?? {} : {};
    push(deviceActivity(prev.current, next, devices, home.now ?? Date.now() / 1000));
    prev.current = next;
  }, [home]);
  useEffect(() => { // IDS output: new alerts and suspicious windows; history already present at load is not replayed
    const first = !seen.current;
    seen.current ??= { alerts: new Set(), windows: new Map() };
    const out: NetEvent[] = [];
    for (const a of state.alerts) if (!seen.current.alerts.has(a.alert_id)) { seen.current.alerts.add(a.alert_id); if (!first) out.push({ at: a.first_seen ?? a.start_ns / 1e9, who: nameOf(a.source_key), what: "security alert raised", tone: "bad" }); }
    for (const w of state.windows.slice(-50) as WindowEvent[]) {
      const last = seen.current.windows.get(w.source_key) ?? 0;
      if (w.state !== "normal" && w.window_end > last + 15) { seen.current.windows.set(w.source_key, w.window_end); if (!first) out.push({ at: w.window_end, who: nameOf(w.source_key), what: "suspicious traffic observed", tone: "warn" }); }
    }
    push(out);
  }, [state.alerts.length, state.windows.length]);
  const now = Date.now() / 1000, fresh = activity.rate != null;
  const rate = state.resources.filter((r) => r.ts > now - 120).map((r) => r.mqtt_msgs_per_s);
  const sources = state.nodes.filter((n) => !n.silent).sort((a, b) => b.msgs_per_s - a.msgs_per_s);
  const max = Math.max(1, ...rate);
  return (
    <section className="card sh-network" aria-label="Live network communication">
      <header className="net-head">
        <div><h2>Network communication</h2><p className="card-sub">Broker MQTT messages counted by the Edge Watch capture</p></div>
        <div className="net-stats">
          <span><b className="num">{fresh ? fmt(activity.rate!, 1) : "—"}</b><small>messages/s (10 s mean)</small></span>
          <span><b className="num">{fresh ? sources.length : "—"}</b><small>network sources (not devices)</small></span>
          {!home?.running && activity.status !== "Disconnected" ? <Pill tone="warn">Hub stopped</Pill> : <Pill tone={activity.status === "Receiving" ? "ok" : activity.status === "No recent traffic" ? "muted" : "warn"}>{activity.status === "Receiving" && <span className="live-dot" />}{activity.status}</Pill>}
        </div>
      </header>
      <div className="net-body">
        <div className="net-graph">
          {rate.length > 1 ? <svg viewBox="0 0 100 30" preserveAspectRatio="none" role="img" aria-label={`Messages per second, last two minutes, peak ${fmt(max, 1)}`}><polyline points={rate.map((v, i) => `${(i / (rate.length - 1)) * 100},${28 - (v / max) * 26}`).join(" ")} vectorEffect="non-scaling-stroke" /></svg>
            : <p className="dim">{home?.running ? "Waiting for the traffic monitor…" : "No hub traffic while the hub is stopped."}</p>}
          <div className="net-sources">{sources.slice(0, 6).map((n) => <span key={n.source_key} className={`chip-dev st-${kindOf(n)}`} title={`${fmt(n.msgs_per_s, 1)} messages/s`}>{nameOf(n.source_key)}</span>)}{sources.length > 6 && <span className="dim">+{sources.length - 6}</span>}</div>
        </div>
        <ol className="net-feed" aria-live="polite">
          {feed.length ? feed.map((e, i) => <li key={`${e.at}-${e.who}-${e.what}-${i}`} className={`tone-${e.tone}`}><time className="num">{clock(e.at)}</time><b>{e.who}</b><span>{e.what}</span></li>)
            : <li className="dim">{home?.running ? "Waiting for device messages…" : "Start the hub to see device messages."}</li>}
        </ol>
      </div>
    </section>
  );
}
