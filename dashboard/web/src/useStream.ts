import { useEffect, useRef, useState } from "react";
import { AlertEvent, apply, Base, empty, removeAlertHistory, State } from "./store";

export const ALERT_HISTORY_CLEARED = "edgewatch-alert-history-cleared";

export interface Health { status: string; store: string; ids: string; ids_enabled?: boolean; run: any; provenance: string | null; model_loaded?: boolean | null; broker_running?: boolean | null; alerts_total?: number | null }

async function json<T>(url: string): Promise<T | null> {
  try {
    const r = await fetch(url);
    return r.ok ? ((await r.json()) as T) : null;
  } catch {
    return null;
  }
}

// REST for the current run, then a WebSocket from the last seen id. Events are buffered and rendered at most 10 times a second.
export function useStream() {
  const [state, setState] = useState<State>(empty);
  const [connected, setConnected] = useState(false);
  const [loading, setLoading] = useState(true);
  const [health, setHealth] = useState<Health | null>(null);
  const [apiDown, setApiDown] = useState(false);
  const buffer = useRef<Base[]>([]);
  const removedAlerts = useRef(new Set<string>());

  useEffect(() => {
    const cleared = (event: Event) => {
      const ids: unknown = (event as CustomEvent).detail;
      if (!Array.isArray(ids) || !ids.every((id) => typeof id === "string")) return;
      ids.forEach((id) => removedAlerts.current.add(id));
      buffer.current = buffer.current.filter((e) => e.event_type !== "alert" || !removedAlerts.current.has((e as AlertEvent).alert_id));
      setState((s) => removeAlertHistory(s, ids));
      json<Health>("/api/health").then((h) => h && setHealth(h)); // the all-history count drops now, not at the next poll
    };
    window.addEventListener(ALERT_HISTORY_CLEARED, cleared);
    return () => window.removeEventListener(ALERT_HISTORY_CLEARED, cleared);
  }, []);

  useEffect(() => {
    let closed = false, socket: WebSocket | null = null, retry: number | undefined, lastId = 0;
    const connect = () => {
      if (closed) return;
      const scheme = location.protocol === "https:" ? "wss" : "ws";
      socket = new WebSocket(`${scheme}://${location.host}/ws/events?after=${lastId}`);
      socket.onopen = () => setConnected(true);
      socket.onmessage = (m) => {
        const events: Base[] = JSON.parse(m.data);
        for (const e of events) if (e.id) lastId = Math.max(lastId, e.id);
        buffer.current.push(...events.filter((e) => e.event_type !== "alert" || !removedAlerts.current.has((e as AlertEvent).alert_id)));
      };
      socket.onclose = () => { setConnected(false); retry = window.setTimeout(connect, 1500); };
    };
    (async () => {
      const h = await json<Health>("/api/health");
      setApiDown(h === null);
      setHealth(h);
      const run = h?.run?.run_id as string | undefined;
      if (run) {
        const q = `run_id=${run}`;
        const [markers, windows, alerts, resources, topology] = await Promise.all([
          json<Base[]>(`/api/markers?${q}`), json<Base[]>(`/api/windows?limit=600&${q}`), json<Base[]>(`/api/alerts?limit=500&${q}`), json<Base[]>(`/api/resources?seconds=86400&${q}`), json<Base>("/api/topology"),
        ]);
        const all = [...(markers ?? []), ...(windows ?? []), ...(resources ?? []), ...(topology && topology.run_id === run ? [topology] : [])];
        all.push(...((alerts ?? []) as Base[]).reverse());
        const ids = all.filter((e) => e.id).map((e) => e.id as number);
        lastId = ids.length ? Math.max(...ids) : 0;
        setState(removeAlertHistory(apply(empty, all, Date.now() / 1000), [...removedAlerts.current]));
      }
      setLoading(false);
      connect();
    })();
    const render = window.setInterval(() => {
      if (buffer.current.length) {
        const batch = buffer.current;
        buffer.current = [];
        setState((s) => apply(s, batch, Date.now() / 1000));
      }
    }, 100);
    const poll = window.setInterval(async () => {
      const h = await json<Health>("/api/health");
      setApiDown(h === null);
      if (h) setHealth(h);
    }, 3000);
    return () => { closed = true; socket?.close(); window.clearTimeout(retry); window.clearInterval(render); window.clearInterval(poll); };
  }, []);

  return { state, connected, loading, health, apiDown };
}

export { json };
