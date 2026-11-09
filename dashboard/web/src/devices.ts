// Smart Home model: device catalogue, floor plan and placement. Pure functions, so the honesty rules are testable.

export type DeviceType = "light" | "motion" | "climate" | "door" | "lock" | "camera" | "plug" | "thermostat" | "smoke";
export type Backing = "software" | "wokwi";
export interface PlacedDevice { id: string; name: string; type: DeviceType; room: RoomId; x: number; y: number; source: Backing }

/**
 * Software devices run in the smart-home hub's device host (lab/devices.py): each one is its own MQTT client with a small,
 * deterministic state machine. wokwi: the device type can instead be backed by the Wokwi ESP32's real sensor or LED.
 * profile is the older lab traffic pattern, kept only for lab.run --mix.
 */
export const TYPES: Record<DeviceType, { label: string; icon: string; profile: string; wokwi?: "climate" | "motion" | "light"; behaviour: string }> = {
  light: { label: "Smart light", icon: "bulb", profile: "light", wokwi: "light", behaviour: "Switches on and off on command and reports its state." },
  motion: { label: "Motion sensor", icon: "motion", profile: "motion", wokwi: "motion", behaviour: "Reports motion, then clear again after a set time." },
  climate: { label: "Temperature sensor", icon: "thermo", profile: "temp_humidity", wokwi: "climate", behaviour: "Reports temperature and humidity every 10 s; for a software sensor you set the room conditions." },
  door: { label: "Door sensor", icon: "door", profile: "door", behaviour: "Reports open and closed, with the time of the last change." },
  lock: { label: "Smart lock", icon: "lock", profile: "door", behaviour: "Locks and unlocks on command and records simulated keypad attempts. No real authentication is implemented." },
  camera: { label: "Camera", icon: "camera", profile: "bursty", behaviour: "Monitoring on or off, and motion-event notifications. There is no video." },
  plug: { label: "Smart plug", icon: "plug", profile: "switch", behaviour: "Switches a connected appliance and reports its simulated power and energy use." },
  thermostat: { label: "Thermostat", icon: "dial", profile: "temp_humidity", behaviour: "Heats or cools the simulated room towards your target temperature." },
  smoke: { label: "Smoke sensor", icon: "smoke", profile: "quiet", behaviour: "Raises a safety alarm when the simulated smoke level passes its threshold, until reset." },
};

export type RoomId = "living" | "kitchen" | "bedroom" | "entrance" | "office" | "bathroom" | "garage";
export const W = 1100, H = 640;
/** Floor plan in canvas units. The space right of the house is outside the home, where a lab attacker is drawn. */
export const ROOMS: { id: RoomId; name: string; x: number; y: number; w: number; h: number }[] = [
  { id: "living", name: "Living room", x: 30, y: 30, w: 400, h: 300 }, { id: "kitchen", name: "Kitchen", x: 430, y: 30, w: 260, h: 300 },
  { id: "bedroom", name: "Bedroom", x: 690, y: 30, w: 250, h: 300 }, { id: "entrance", name: "Entrance", x: 30, y: 330, w: 260, h: 280 },
  { id: "office", name: "Office", x: 290, y: 330, w: 280, h: 280 }, { id: "bathroom", name: "Bathroom", x: 570, y: 330, w: 150, h: 280 },
  { id: "garage", name: "Garage", x: 720, y: 330, w: 220, h: 280 },
];
export const HUB = { x: 430, y: 330 }; // where the walls meet: the home's network closet
export const ATTACKER = { x: 1025, y: 330 };
export const MAX_DEVICES = 24, MAX_SOFTWARE = 20;
const MARGIN = 38, SPACING = 105, GRID = 10; // spacing leaves room for the name under each tile

export const roomAt = (x: number, y: number) => ROOMS.find((r) => x >= r.x && x < r.x + r.w && y >= r.y && y < r.y + r.h)?.id ?? null;
const roomOf = (id: RoomId) => ROOMS.find((r) => r.id === id)!;

/** A free spot near (x, y) inside the room there, snapped to a grid and away from other devices. Null outside the house. */
export function place(devices: PlacedDevice[], x: number, y: number, ignore?: string, room?: RoomId) {
  const r = roomOf(room ?? roomAt(x, y) ?? ("" as RoomId));
  if (!r) return null;
  const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v));
  const others = devices.filter((d) => d.id !== ignore && !(Math.abs(d.x - HUB.x) < 1 && Math.abs(d.y - HUB.y) < 1));
  const free = (px: number, py: number) => Math.hypot(px - HUB.x, py - HUB.y) > SPACING && others.every((d) => Math.hypot(d.x - px, d.y - py) >= SPACING);
  const snap = (v: number) => Math.round(v / GRID) * GRID;
  const bx = clamp(snap(x), r.x + MARGIN, r.x + r.w - MARGIN), by = clamp(snap(y), r.y + MARGIN + 14, r.y + r.h - MARGIN);
  if (free(bx, by)) return { x: bx, y: by, room: r.id };
  // Every grid point in the room, nearest to the drop first: finds a free spot whenever one exists.
  const spots: [number, number][] = [];
  for (let px = Math.ceil((r.x + MARGIN) / GRID) * GRID; px <= r.x + r.w - MARGIN; px += GRID * 2)
    for (let py = Math.ceil((r.y + MARGIN + 14) / GRID) * GRID; py <= r.y + r.h - MARGIN; py += GRID * 2) spots.push([px, py]);
  spots.sort((a, c) => Math.hypot(a[0] - bx, a[1] - by) - Math.hypot(c[0] - bx, c[1] - by));
  const spot = spots.find(([px, py]) => free(px, py));
  return spot ? { x: spot[0], y: spot[1], room: r.id } : { x: bx, y: by, room: r.id }; // a full room: allow an overlap rather than refuse the drop
}

/** Never reused, so a new device cannot inherit what a removed one left behind (saved state, IDS history). Max 12 chars. */
export function newId(devices: PlacedDevice[], now = Date.now()) {
  const stem = `d${now.toString(36).slice(-7)}`;
  let n = devices.length;
  while (devices.some((d) => d.id === `${stem}${n}`)) n++;
  return `${stem}${n}`;
}
/** The lowest unused number, so a name is never repeated after devices are removed. */
export function defaultName(devices: PlacedDevice[], type: DeviceType) {
  let n = 1;
  while (devices.some((d) => d.name === `${TYPES[type].label} ${n}`)) n++;
  return `${TYPES[type].label} ${n}`;
}
export const canBeWokwi = (devices: PlacedDevice[], type: DeviceType, self?: string) => !!TYPES[type].wokwi && !devices.some((d) => d.id !== self && d.source === "wokwi" && d.type === type);

export function addDevice(devices: PlacedDevice[], type: DeviceType, x: number, y: number, room?: RoomId): PlacedDevice[] {
  if (devices.length >= MAX_DEVICES) return devices;
  const spot = place(devices, x, y, undefined, room);
  if (!spot) return devices;
  return [...devices, { id: newId(devices), name: defaultName(devices, type), type, room: spot.room, x: spot.x, y: spot.y, source: "software" }];
}

/** The lab mix for a layout: each software device as profile@id, so its traffic source maps back to it. Wokwi devices are the ESP32 itself. */
export const mixFor = (devices: PlacedDevice[]) => devices.filter((d) => d.source === "software").slice(0, MAX_SOFTWARE).map((d) => `${TYPES[d.type].profile}@${d.id}`);

/** Layout device id -> source key, from the IDS's pseudonymized device labels ("light@d3"). The latest label for an id wins. */
export function linkSources(labels: Record<string, string>): Map<string, string> {
  const out = new Map<string, string>();
  for (const [key, label] of Object.entries(labels)) {
    const at = label.indexOf("@");
    if (at > 0) out.set(label.slice(at + 1), key);
  }
  return out;
}

export function sampleHome(wokwi: boolean): PlacedDevice[] {
  const seed: [DeviceType, RoomId, number, number, Backing][] = [
    ["climate", "living", 150, 120, wokwi ? "wokwi" : "software"], ["light", "living", 300, 220, wokwi ? "wokwi" : "software"], ["motion", "entrance", 140, 440, wokwi ? "wokwi" : "software"],
    ["door", "entrance", 110, 550, "software"], ["lock", "entrance", 220, 550, "software"], ["camera", "garage", 830, 450, "software"],
    ["plug", "kitchen", 560, 140, "software"], ["thermostat", "bedroom", 820, 140, "software"], ["smoke", "kitchen", 600, 260, "software"],
  ];
  let devices: PlacedDevice[] = [];
  for (const [type, room, x, y, source] of seed) {
    devices = addDevice(devices, type, x, y, room);
    devices[devices.length - 1].source = source;
  }
  return devices.map((d) => (d.source === "wokwi" ? { ...d, name: `${TYPES[d.type].label} (Wokwi)` } : d));
}

/** Short text for a device tile, from the device's own reported state. */
export function summary(type: DeviceType, s: Record<string, any>): string {
  switch (type) {
    case "light": return s.on ? "On" : "Off";
    case "motion": return s.motion ? "Motion detected" : "Clear";
    case "climate": return `${Number(s.temperature).toFixed(1)} °C · ${Number(s.humidity).toFixed(0)} %`;
    case "door": return s.open ? "Open" : "Closed";
    case "lock": return s.locked ? "Locked" : "Unlocked";
    case "camera": return s.monitoring ? "Monitoring" : "Paused";
    case "plug": return s.on ? `${Number(s.power_w).toFixed(0)} W (simulated)` : "Off";
    case "thermostat": return `${Number(s.current).toFixed(1)} °C ${s.mode === "idle" ? "· at target" : `· ${s.mode}`}`;
    case "smoke": return s.alarm ? "SMOKE ALARM" : `Clear · level ${Number(s.level).toFixed(0)}`;
  }
}

/** Visual classes for a device's own state (light glow, open door, alarm...), separate from Edge Watch's verdict on its traffic. */
export function look(type: DeviceType, s: Record<string, any>): { classes: string[]; icon: string } {
  const icon = type === "door" && s.open ? "doorOpen" : type === "lock" && !s.locked ? "unlock" : TYPES[type].icon;
  const classes = [
    (type === "light" || type === "plug") && s.on ? "dv-on" : "", type === "motion" && s.motion ? "dv-motion" : "",
    (type === "door" && s.open) || (type === "lock" && !s.locked) ? "dv-open" : "", type === "camera" && s.monitoring ? "dv-rec" : "",
    type === "thermostat" && s.mode === "heating" ? "dv-heat" : "", type === "thermostat" && s.mode === "cooling" ? "dv-cool" : "",
    type === "smoke" && s.alarm ? "dv-alarm" : "",
  ].filter(Boolean);
  return { classes, icon };
}
