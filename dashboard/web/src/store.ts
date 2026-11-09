// Client state: pure reducer plus helpers, so the honesty rules can be tested without a browser.

export type Provenance = "live" | "replay" | "synthetic";
export interface Base { id?: number; event_type: string; ts: number; run_id: string; provenance?: Provenance; traffic_source?: string; schema_version?: string }
export type Stage = { window_close_to_features: number; inference: number; alert_build: number; processing_total: number };
export interface WindowEvent extends Base { window_id: string; window_start: number; window_end: number; source_key: string; features: Record<string, number>; complete: boolean; prediction: string | null; score: number | null; state: "normal" | "suspicious" | "alert"; model_id: string | null; ground_truth: string | null; stage_latency_ms: Stage }
export interface Evidence { feature: string; value: number; baseline_p50: number | null; contribution: number | null }
export interface AlertEvent extends Base { alert_id: string; source_key: string; kind: "model" | "rule"; predicted_class: string; score: number | null; severity: "low" | "medium" | "high"; start_ns: number; last_window_ns: number; duration_s: number; window_ids: string[]; evidence: Evidence[]; status: "unverified_prediction" | "matches_scheduled_attack" | "no_scheduled_attack"; model_id: string | null; first_seen: number }
export interface ResourceEvent extends Base { ids_cpu_pct: number; ids_rss_mb: number; capture_cpu_pct: number | null; capture_rss_mb: number | null; broker_running: boolean; broker_cpu_pct: number | null; broker_rss_mb: number | null; soc_temp_c: number | null; throttled: boolean | null; pkts_per_s: number; mqtt_msgs_per_s: number; windows_per_s: number; capture_drops_total: number | null; tcp_gaps_total: number; malformed_frames_total: number; tracked_f22_connections: number; model_errors: number; store_write_errors: number; model_loaded: boolean; ids_enabled: boolean }
export interface MarkerEvent extends Base { marker: string; scenario?: string; model_id?: string | null; family?: string; source_key?: string; start_ns?: number; end_ns?: number; label?: string; window_s?: number; episode?: number; devices?: Record<string, string> }
export interface TopologyNode { source_key: string; msgs_per_s: number; state?: string; score?: number | null; predicted?: string | null; silent: boolean }
export interface TopologyEvent extends Base { nodes: TopologyNode[] }

export interface State {
  runId: string | null; run: MarkerEvent | null; windows: WindowEvent[]; alerts: AlertEvent[]; resources: ResourceEvent[]; markers: MarkerEvent[];
  nodes: TopologyNode[]; order: string[]; provenances: Provenance[]; missingProvenance: boolean; lastTs: number | null; lastReceived: number | null; lastId: number;
}

export const empty: State = { runId: null, run: null, windows: [], alerts: [], resources: [], markers: [], nodes: [], order: [], provenances: [], missingProvenance: false, lastTs: null, lastReceived: null, lastId: 0 };
const MAX_WINDOWS = 1200, MAX_RESOURCES = 1800;

// Applied in arrival order. A new run_start resets the view, so two runs are never shown as one.
export function apply(s: State, events: Base[], now: number): State {
  let n: State = { ...s };
  for (const e of events) {
    if (e.id != null) n.lastId = Math.max(n.lastId, e.id);
    const isStart = e.event_type === "run_marker" && (e as MarkerEvent).marker === "run_start";
    if (isStart && e.run_id !== n.runId) n = { ...empty, lastId: n.lastId, runId: e.run_id, run: e as MarkerEvent };
    if (n.runId === null) n.runId = e.run_id;
    if (e.run_id !== n.runId && !isStart) continue;
    if (!e.provenance) n.missingProvenance = true;
    else if (!n.provenances.includes(e.provenance)) n.provenances = [...n.provenances, e.provenance];
    n.lastTs = Math.max(n.lastTs ?? 0, e.ts); n.lastReceived = now; // alerts carry their window's start, which is older than the newest event
    switch (e.event_type) {
      case "window": {
        const w = e as WindowEvent;
        n.windows = [...n.windows.slice(-MAX_WINDOWS + 1), w];
        if (!n.order.includes(w.source_key)) n.order = [...n.order, w.source_key];
        break;
      }
      case "alert": {
        const a = e as AlertEvent;
        n.alerts = [a, ...n.alerts.filter((x) => x.alert_id !== a.alert_id)];
        break;
      }
      case "resource": n.resources = [...n.resources.slice(-MAX_RESOURCES + 1), e as ResourceEvent]; break;
      case "run_marker": n.markers = [...n.markers, e as MarkerEvent]; break;
      case "topology": {
        n.nodes = (e as TopologyEvent).nodes;
        const fresh = n.nodes.map((x) => x.source_key).filter((k) => !n.order.includes(k));
        if (fresh.length) n.order = [...n.order, ...fresh];
        break;
      }
    }
  }
  return n;
}

export function provenanceState(s: State): "ok" | "none" | "error" {
  if (s.missingProvenance || s.provenances.length > 1) return "error";
  return s.provenances.length ? "ok" : "none";
}

export function percentile(values: number[], p: number): number | null {
  if (!values.length) return null;
  const sorted = [...values].sort((a, b) => a - b);
  return sorted[Math.min(sorted.length - 1, Math.floor(p * sorted.length))];
}

const SEVERITY = { high: 0, medium: 1, low: 2 };
export function alertOrder(alerts: AlertEvent[]): AlertEvent[] {
  return [...alerts].sort((a, b) => SEVERITY[a.severity] - SEVERITY[b.severity] || b.start_ns - a.start_ns);
}

export const FEATURE_NAMES: Record<string, string> = { F01: "packets", F02: "bytes", F03: "SYN", F04: "RST", F05: "FIN", F06: "distinct ports", F07: "IAT mean", F08: "IAT std", F09: "CONNECT", F10: "refused CONNACK", F11: "refused ratio", F12: "PUBLISH", F13: "SUBSCRIBE", F14: "PINGREQ", F15: "DISCONNECT", F16: "MQTT len mean", F17: "MQTT len std", F18: "MQTT len max", F19: "distinct topics", F20: "QoS>0 fraction", F21: "retain fraction", F22: "keep-alive max", F23: "malformed", F24: "wildcard subscribes", F25: "broker messages", F26: "active sources" };

// Command-center helpers. Every number is computed from received events; nothing is estimated or filled in.

/** Simulated device profiles announced by the lab runner (pseudonymized by the IDS). Metadata only, never detection input. */
export function devicesOf(s: State): Record<string, string> {
  return [...s.markers].reverse().find((m) => m.marker === "scenario_devices")?.devices ?? {};
}

export function overview(s: State) {
  const end = s.windows.at(-1)?.window_end ?? 0;
  const active = s.nodes.length ? s.nodes.filter((n) => !n.silent).length : new Set(s.windows.filter((w) => w.window_end > end - 15).map((w) => w.source_key)).size;
  const severity = { high: 0, medium: 0, low: 0 };
  for (const a of s.alerts) severity[a.severity]++;
  return {
    activeSources: active, observedSources: s.order.length, msgsPerS: s.resources.at(-1)?.mqtt_msgs_per_s ?? null, alerts: s.alerts.length, severity,
    matched: s.alerts.filter((a) => a.status === "matches_scheduled_attack").length, unmatched: s.alerts.filter((a) => a.status === "no_scheduled_attack").length,
    scheduled: s.markers.filter((m) => m.marker === "scheduled_attack").length,
  };
}

/** Each scheduled episode with the first model alert from its source that overlaps it. Time to detect runs from attack start to the end of the alert's k-th window. */
export function episodeOutcomes(s: State) {
  return s.markers.filter((m) => m.marker === "scheduled_attack").map((m) => {
    const hit = s.alerts.filter((a) => a.kind === "model" && a.source_key === m.source_key && a.start_ns < m.end_ns! + 5e9 && a.last_window_ns + 5e9 > m.start_ns! - 5e9).sort((a, b) => a.start_ns - b.start_ns)[0];
    return { marker: m, alert: hit ?? null, ttd: hit ? (hit.start_ns + 2 * 5e9 - m.start_ns!) / 1e9 : null };
  });
}

// Plain-language layer for the customer views. Wording describes what was observed; it never claims intent or that traffic was stopped.

export const CLASS_TEXT: Record<string, { title: string; what: string; risk: string }> = {
  flood: { title: "Unusually high message traffic", what: "This source sent far more messages or connection requests than normal smart devices do in the same few seconds.", risk: "A flood like this can slow down or overwhelm the message hub, so messages from real devices may be delayed or lost." },
  bruteforce: { title: "Repeated login attempts", what: "This source tried to sign in to the message hub many times, and many of those attempts were refused.", risk: "Repeated guessing can be an attempt to find a valid password. It may also be a misconfigured device." },
  malformed: { title: "Unexpected message format", what: "Messages from this source did not follow the MQTT message format that smart devices normally use.", risk: "Broken messages can be an attempt to crash or confuse the hub or other devices. They can also come from faulty software." },
  lowrate: { title: "Connections held open unusually long", what: "This source opened connections and kept them alive while sending almost nothing.", risk: "Holding many idle connections can slowly use up the hub's capacity so real devices cannot connect." },
  wildcard_subscribe: { title: "Listening to every device", what: "This source subscribed with a wildcard topic, which asks the hub for messages from many devices at once.", risk: "It could expose readings from other devices if access rules are loose. Some monitoring tools do this legitimately." },
};
export const classText = (c: string) => CLASS_TEXT[c] ?? { title: c.replaceAll("_", " "), what: "Edge Watch's detector flagged this source's traffic as unlike normal device traffic.", risk: "The pattern differs from normal traffic. Review the technical details before drawing conclusions." };

export const STATUS_PLAIN: Record<AlertEvent["status"], string> = { matches_scheduled_attack: "Matches a simulated attack", no_scheduled_attack: "No simulated attack was scheduled: possible false alarm", unverified_prediction: "Not checked against a demo schedule" };

/** Device profiles the lab runner announces. Labels are simulated profiles, never a verified physical device. */
export const PROFILE: Record<string, { label: string; icon: string; single?: boolean }> = {
  temp_humidity: { label: "Temperature sensor", icon: "thermo" }, motion: { label: "Motion sensor", icon: "motion" }, light: { label: "Smart light", icon: "bulb" },
  switch: { label: "Smart switch", icon: "switch" }, door: { label: "Door sensor", icon: "door" }, quiet: { label: "Idle device", icon: "moon" },
  steady: { label: "Sensor", icon: "chip" }, slow: { label: "Slow sensor", icon: "chip" }, bursty: { label: "Bursty sensor", icon: "wave" }, qos1: { label: "Reliable sensor", icon: "chip" },
  qos2: { label: "Reliable sensor", icon: "chip" }, retained: { label: "Status reporter", icon: "chip" }, reconnecting: { label: "Reconnecting device", icon: "refresh" },
  // lab.home: the Wokwi gateway's connection (one simulated ESP32) and Edge Watch's own read-only telemetry reader
  climate: { label: "Temperature sensor", icon: "thermo" }, lock: { label: "Smart lock", icon: "lock" }, camera: { label: "Camera", icon: "camera" },
  plug: { label: "Smart plug", icon: "plug" }, thermostat: { label: "Thermostat", icon: "dial" }, smoke: { label: "Smoke sensor", icon: "smoke" },
  wokwi_esp32: { label: "Wokwi ESP32 smart home", icon: "home", single: true }, wokwi_serial: { label: "Wokwi ESP32 (serial bridge)", icon: "home", single: true }, edgewatch_bridge: { label: "Edge Watch telemetry reader", icon: "shield", single: true },
};

export interface Device { key: string; name: string; icon: string; kind: "profile" | "attacker" | "unknown"; profile: string | null; family: string | null; layoutId?: string }

/** Friendly names: "Motion sensor 2" from the runner's profile map, "Lab attacker" for scheduled attack sources, otherwise unknown. */
/** layout: the Smart Home devices; a source labelled "profile@id" by a layout run takes that device's name and icon. */
export function deviceDirectory(s: State, layout: { id: string; name: string; icon: string }[] = []): Map<string, Device> {
  const devices = devicesOf(s), seen: Record<string, number> = {}, out = new Map<string, Device>();
  for (const [key, label] of Object.entries(devices)) {
    const [profile, layoutId] = label.split("@");
    const placed = layoutId ? layout.find((d) => d.id === layoutId) : undefined;
    const p = PROFILE[profile] ?? { label: profile.replaceAll("_", " "), icon: "chip" };
    seen[p.label] = (seen[p.label] ?? 0) + 1;
    // a layout id that is no longer placed: say so, rather than reuse a name a current device may have
    const name = placed ? placed.name : layoutId && layout.length ? `Removed ${p.label.toLowerCase()}` : "single" in p && p.single ? p.label : `${p.label} ${seen[p.label]}`;
    out.set(key, { key, name, icon: placed?.icon ?? p.icon, kind: "profile", profile, family: null, layoutId });
  }
  for (const m of s.markers) if (m.marker === "scheduled_attack" && m.source_key && !out.has(m.source_key)) out.set(m.source_key, { key: m.source_key, name: `Lab attacker: ${scenarioText(m.family ?? "").name.toLowerCase()}`, icon: "attack", kind: "attacker", profile: null, family: m.family ?? null });
  for (const key of s.order) if (!out.has(key)) out.set(key, { key, name: `Unknown device ${key.slice(-4)}`, icon: "unknown", kind: "unknown", profile: null, family: null });
  return out;
}

export const SCENARIO_TEXT: Record<string, { name: string; text: string }> = {
  flood_publish: { name: "Message flooding", text: "A simulated attacker sends an unusually large number of messages, which can overwhelm the hub every device relies on." },
  bruteforce: { name: "Repeated login attempts", text: "A simulated attacker keeps guessing the password of a disposable lab account on the hub." },
  malformed: { name: "Malformed messages", text: "A simulated attacker sends broken messages that do not follow the MQTT format." },
  flood_connect: { name: "Suspicious connection activity", text: "A simulated attacker opens and drops connections very quickly, straining the hub." },
  lowrate: { name: "Low-rate connection hold", text: "A simulated attacker quietly holds connections open to use up the hub's capacity." },
  topic_probe: { name: "Topic exploration", text: "A simulated attacker probes many topic names to map the home. The AI model was not trained on this, so it may go undetected." },
  wildcard: { name: "Listening to every device", text: "A simulated attacker subscribes to all topics. Only a simple rule watches for this; the AI model was not trained on it." },
};
export const scenarioText = (f: string) => SCENARIO_TEXT[f] ?? { name: f.replaceAll("_", " "), text: "" };

export const FEATURE_PLAIN: Record<string, string> = {
  F01: "Network packets", F02: "Data volume (bytes)", F03: "New connection attempts", F04: "Connection resets", F05: "Connection closes", F06: "Different ports used", F07: "Average gap between packets",
  F08: "Variation in packet gaps", F09: "Sign-in requests", F10: "Refused sign-ins", F11: "Share of refused sign-ins", F12: "Messages published", F13: "Subscriptions", F14: "Keep-alive pings", F15: "Disconnects",
  F16: "Average message size", F17: "Variation in message size", F18: "Largest message", F19: "Different topics", F20: "Messages needing delivery receipts", F21: "Retained messages", F22: "Longest keep-alive setting",
  F23: "Malformed packets", F24: "Wildcard subscriptions", F25: "All hub messages", F26: "Devices active on the network",
};

export type MonitorState = "offline" | "not_started" | "paused" | "stopped" | "alert" | "monitoring";
/** Headline status from backend facts only. No recent alert means nothing was flagged, not that the network is proven safe. */
export function monitorState(h: { status: string; ids: string; ids_enabled?: boolean } | null, connected: boolean, s: State, now: number, recentS = 120): MonitorState {
  if (!h || !connected) return "offline";
  if (h.status === "no_store") return "not_started";
  if (h.ids_enabled === false) return "paused";
  if (s.alerts.some((a) => now - a.last_window_ns / 1e9 < recentS)) return "alert";
  return h.ids === "running" ? "monitoring" : "stopped";
}

/** Demo progress from events only: a stage is reached when its evidence exists, so a missed attack never shows "alert raised". */
export function demoStages(s: State, since: number, now: number) {
  const attacks = s.markers.filter((m) => m.marker === "scheduled_attack" && m.start_ns! / 1e9 >= since - 1);
  const begun = attacks.filter((m) => m.start_ns! / 1e9 <= now);
  const suspicious = s.windows.some((w) => w.state !== "normal" && begun.some((m) => m.source_key === w.source_key && w.window_end > m.start_ns! / 1e9));
  const outcomes = episodeOutcomes(s).filter((o) => o.marker.start_ns! / 1e9 >= since - 1);
  return { normal: s.windows.some((w) => w.window_end >= since), scheduled: attacks.length, begun: begun.length, suspicious, alerted: outcomes.filter((o) => o.alert).length, outcomes };
}
