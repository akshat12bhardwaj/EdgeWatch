import { Component, ReactNode, useEffect, useMemo, useRef, useState } from "react";
import { Canvas, ThreeEvent, useFrame, useThree } from "@react-three/fiber";
import { Html, Line, OrbitControls, RoundedBox } from "@react-three/drei";
import { OrbitControls as OrbitImpl } from "three-stdlib";
import { CanvasTexture, Plane, Raycaster, RepeatWrapping, SRGBColorSpace, Vector2, Vector3 } from "three";
import { ATTACKER, CONTROLLERS, DeviceType, HUB, place, PlacedDevice, ROOMS, TYPES } from "./devices";
import type { Live, useAttacker } from "./smarthome";
import "./home3d.css";
type Point = [number, number, number];
type Attacker = (NonNullable<ReturnType<typeof useAttacker>> & { delay?: number | null; outcome?: "processing" | "alert" | "missed" }) | null;
export interface Home3DProps {
  devices: PlacedDevice[]; live: Map<string, Live>; attacker: Attacker;
  selected?: string | null; onSelect?: (id: string | null) => void;
  onChange?: (devices: PlacedDevice[]) => void;
  deviceList?: boolean; // false when the page shows its own device list
  placementType?: DeviceType | null;
  onPlace?: (type: DeviceType, x: number, y: number) => void;
  fallback: ReactNode;
}
// The saved 2D coordinate system remains authoritative. No layout migration is needed.
const world = (x: number, y: number, height = 0): Point => [(x - 485) / 65, height, (y - 320) / 65];
const plan = (v: Vector3) => ({ x: v.x * 65 + 485, y: v.z * 65 + 320 });
const WALL = "#f0eee6", OAK = "#bc9570", FRAME = "#364146";
const COLORS: Record<string, string> = { alert: "#ff657c", suspicious: "#f8c065", normal: "#48d9bd", quiet: "#6fabc3", idle: "#738295", offline: "#738295" };
const CAMERA: Point = [8.6, 20.5, 13.8];

class SceneBoundary extends Component<{ children: ReactNode; fallback: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  render() { return this.state.failed ? <div className="scene-fallback"><p role="status">3D is unavailable. Select a device below to use its controls.</p>{this.props.fallback}</div> : this.props.children; }
}

function Box({ at, size, color, emissive, rotation = 0 }: { at: Point; size: Point; color: string; emissive?: string; rotation?: number }) {
  return <mesh position={at} rotation={[0, rotation, 0]} castShadow receiveShadow><boxGeometry args={size} /><meshStandardMaterial color={color} roughness={0.72} metalness={0.12} emissive={emissive ?? "#000000"} emissiveIntensity={emissive ? 0.65 : 0} /></mesh>;
}

function Cylinder({ at, radius, height, color, glow = false }: { at: Point; radius: number; height: number; color: string; glow?: boolean }) {
  return <mesh position={at} castShadow receiveShadow><cylinderGeometry args={[radius, radius, height, 20]} /><meshStandardMaterial color={color} roughness={0.6} metalness={0.2} emissive={glow ? color : "#000000"} emissiveIntensity={glow ? 0.8 : 0} /></mesh>;
}
/** Original procedural finishes and geometry; no third-party model, texture or font downloads. */

function floorTexture(tile: boolean) {
  const canvas = document.createElement("canvas"); canvas.width = canvas.height = 512;
  const c = canvas.getContext("2d")!;
  let seed = 31; const rand = () => { seed = (seed * 16807) % 2147483647; return seed / 2147483647; };
  c.fillStyle = tile ? "#dcded9" : "#c8b298"; c.fillRect(0, 0, 512, 512);
  if (tile) {
    for (let y = 0; y < 4; y++) for (let x = 0; x < 4; x++) {
      const v = 222 + Math.floor(rand() * 12); c.fillStyle = `rgb(${v},${v + 1},${v - 3})`;
      c.fillRect(x * 128 + 1, y * 128 + 1, 126, 126);
    }
    for (let i = 0; i < 4000; i++) { c.fillStyle = rand() > .5 ? "#ffffff0b" : "#7d827b0c"; c.fillRect(rand() * 512, rand() * 512, 1, 1); }
  } else {
    const colors = ["#d7c3a9", "#ceba9f", "#dbc9b1", "#cfb99c", "#d4bea4"];
    for (let row = 0; row < 10; row++) {
      c.fillStyle = colors[row % colors.length]; c.fillRect(0, row * 51.2 + 1, 512, 50);
      c.strokeStyle = "#8b745323"; c.lineWidth = .7;
      const end = row % 2 ? 170 : 340; c.beginPath(); c.moveTo(end, row * 51.2); c.lineTo(end, row * 51.2 + 51.2); c.stroke();
      for (let line = 0; line < 11; line++) {
        const y = row * 51.2 + rand() * 48; c.strokeStyle = rand() > .5 ? "#87704c15" : "#fff9e719";
        c.beginPath(); c.moveTo(0, y); c.bezierCurveTo(140, y + rand() * 5, 350, y - rand() * 5, 512, y + rand() * 2); c.stroke();
      }
    }
  }
  const t = new CanvasTexture(canvas); t.wrapS = t.wrapT = RepeatWrapping; t.colorSpace = SRGBColorSpace; t.anisotropy = 4;
  return t;
}

function Floor({ room }: { room: typeof ROOMS[number] }) {
  const tiled = ["bathroom", "kitchen", "garage"].includes(room.id), texture = useMemo(() => floorTexture(tiled), [tiled]);
  texture.repeat.set(room.w / (tiled ? 190 : 260), room.h / (tiled ? 190 : 260));
  useEffect(() => () => texture.dispose(), [texture]);
  return <mesh rotation={[-Math.PI / 2, 0, 0]} position={world(room.x + room.w / 2, room.y + room.h / 2, .165)} receiveShadow><planeGeometry args={[room.w / 65 - .04, room.h / 65 - .04]} /><meshStandardMaterial map={texture} roughness={.88} /></mesh>;
}

function Soft({ at, size, color, rotation = 0, radius = .08 }: { at: Point; size: Point; color: string; rotation?: number; radius?: number }) {
  return <RoundedBox position={at} args={size} radius={radius} smoothness={2} rotation={[0, rotation, 0]} castShadow receiveShadow><meshStandardMaterial color={color} roughness={.95} /></RoundedBox>;
}

function Plant({ at, scale = 1 }: { at: Point; scale?: number }) {
  return <group position={at} scale={scale}>
    <mesh position={[0, .25, 0]} castShadow><cylinderGeometry args={[.23, .17, .4, 12]} /><meshStandardMaterial color="#d7c9b4" roughness={.9} /></mesh>
    <Cylinder at={[0, .46, 0]} radius={.19} height={.02} color="#5a4937" />
    {[0, 1, 2, 3, 4].map((n) => <group key={n} rotation={[0, n * 2.4, .3]}><mesh position={[.17, .76 + (n % 2) * .2, 0]} rotation={[0, 0, -.45]} scale={[.19, .43, .09]} castShadow><sphereGeometry args={[1, 8, 6]} /><meshStandardMaterial color={n % 2 ? "#62816a" : "#48694e"} roughness={1} /></mesh></group>)}
  </group>;
}

function Table({ at, width = 1.6, depth = .85, height = .8, color = OAK }: { at: Point; width?: number; depth?: number; height?: number; color?: string }) {
  return <group position={at}><Soft at={[0, height, 0]} size={[width, .09, depth]} color={color} radius={.04} />{[-1, 1].flatMap((x) => [-1, 1].map((z) => <Box key={`${x}${z}`} at={[x * (width / 2 - .12), height / 2, z * (depth / 2 - .12)]} size={[.07, height, .07]} color={color} />))}</group>;
}

function Chair({ at, rotation = 0, color = "#a9b6b4" }: { at: Point; rotation?: number; color?: string }) {
  return <group position={at} rotation={[0, rotation, 0]}><Soft at={[0, .48, 0]} size={[.57, .12, .6]} color={color} radius={.05} /><Soft at={[0, .8, -.25]} size={[.57, .62, .1]} color={color} radius={.04} />{[-.21, .21].flatMap((x) => [-.21, .21].map((z) => <Box key={`${x}${z}`} at={[x, .23, z]} size={[.05, .46, .05]} color={OAK} />))}</group>;
}

function Lamp({ at, floor = false }: { at: Point; floor?: boolean }) {
  return <group position={at}><Cylinder at={[0, .05, 0]} radius={floor ? .25 : .13} height={.06} color="#766d5b" /><Cylinder at={[0, floor ? .7 : .22, 0]} radius={.025} height={floor ? 1.4 : .4} color="#887d65" /><mesh position={[0, floor ? 1.55 : .48, 0]} castShadow><cylinderGeometry args={[floor ? .29 : .18, floor ? .39 : .23, floor ? .45 : .32, 20]} /><meshStandardMaterial color="#f3e9d6" roughness={.9} emissive="#9a7952" emissiveIntensity={.12} /></mesh></group>;
}

function Furniture({ room }: { room: string }) {
  if (room === "living") return <>
    <Soft at={[-4.9, .18, -2.65]} size={[3.4, .02, 2.4]} color="#e0dfd4" radius={.01} />
    <Soft at={[-4.9, .4, -3.6]} size={[2.8, .42, .85]} color="#b9c3bd" />
    <Soft at={[-4.9, .82, -3.91]} size={[2.8, .72, .17]} color="#b9c3bd" />
    {[-6.22, -3.58].map(x => <Soft key={x} at={[x, .62, -3.55]} size={[.19, .52, .95]} color="#b9c3bd" radius={.05} />)}
    {[-5.75, -4.9, -4.05].map(x => <Soft key={x} at={[x, .65, -3.49]} size={[.79, .16, .65]} color="#e0e3d9" />)}
    <Table at={[-4.9, .18, -2.2]} width={1.25} depth={.65} height={.35} color="#bda484" />
    <Box at={[-4.9, .35, -.45]} size={[2.2, .35, .38]} color={OAK} /><Box at={[-4.9, .91, -.55]} size={[1.55, .78, .06]} color="#364344" /><Box at={[-4.9, .91, -.51]} size={[1.44, .67, .012]} color="#536c6c" />
  </>;
  if (room === "kitchen") return <>
    <Box at={[.7, .65, -3.98]} size={[2.75, .95, .65]} color="#e6e5dc" /><Box at={[.7, 1.17, -3.98]} size={[2.83, .09, .72]} color="#f3f0e7" />
    {[-.25, .65, 1.55].map(x => <Box key={x} at={[x, .65, -3.64]} size={[.82, .82, .025]} color="#d8d8cc" />)}
    <Box at={[1.25, 1.23, -3.98]} size={[.65, .025, .42]} color="#8d9c99" /><Box at={[1.25, 1.25, -3.98]} size={[.5, .02, .3]} color="#c1ceca" /><Cylinder at={[1.25, 1.4, -4.16]} radius={.025} height={.32} color="#83908d" />
    <Box at={[-.25, 1.23, -3.98]} size={[.6, .02, .44]} color="#414a49" />
    <Box at={[2.57, 1.05, -3.82]} size={[.7, 1.74, .72]} color="#c4cfca" /><Box at={[2.57, 1.14, -3.44]} size={[.63, 1.5, .025]} color="#e6e8df" />
    <Table at={[1.25, .18, -1.4]} width={1.25} depth={.75} /><Chair at={[1.25, .18, -.65]} />
  </>;
  if (room === "bedroom") return <>
    <Soft at={[5.05, .185, -2.65]} size={[2.7, .02, 3.35]} color="#e8e2d6" radius={.01} />
    <Soft at={[5.05, .4, -2.8]} size={[1.9, .42, 2.4]} color="#b6a88e" radius={.05} /><Soft at={[5.05, .69, -2.8]} size={[1.86, .23, 2.35]} color="#f5f1e5" />
    <Soft at={[5.05, .91, -3.99]} size={[2.05, 1.1, .12]} color="#baafa1" radius={.04} /><Soft at={[5.05, .85, -2.35]} size={[1.9, .1, 1.2]} color="#a7b8af" radius={.04} />
    {[4.55, 5.55].map(x => <Soft key={x} at={[x, .87, -3.52]} size={[.72, .17, .48]} color="#fff8e9" radius={.07} />)}
    <Box at={[6.35, .42, -3.55]} size={[.5, .5, .55]} color={OAK} /><Lamp at={[6.35, .7, -3.55]} />
  </>;
  if (room === "entrance") return <>
    <Soft at={[-5.2, .18, 2.7]} size={[1.4, .02, 2.2]} color="#c7c0af" radius={.01} /><Table at={[-6.55, .18, 2.7]} width={.4} depth={1.4} height={.72} />
    <Plant at={[-6.4, .18, .75]} scale={.8} /><Box at={[-4.8, .92, 4.43]} size={[1.15, 1.48, .1]} color="#b39875" />
  </>;
  if (room === "office") return <>
    <Table at={[-.65, .18, 3.8]} width={2.5} depth={.7} height={.82} /><Box at={[-.65, 1.32, 3.92]} size={[1, .58, .06]} color="#404e50" /><Box at={[-.65, 1.32, 3.88]} size={[.91, .49, .012]} color="#729291" /><Chair at={[-.65, .18, 2.75]} rotation={Math.PI} color="#97aba1" />
  </>;
  if (room === "bathroom") return <>
    <Box at={[2.9, .23, 3.55]} size={[1, .12, 1.35]} color="#c8d8d0" /><mesh position={[2.35, .9, 3.55]}><boxGeometry args={[.025, 1.45, 1.35]} /><meshPhysicalMaterial color="#c1dbe0" transparent opacity={.19} roughness={.12} depthWrite={false} /></mesh>
    <Soft at={[1.88, .43, .85]} size={[.52, .4, .75]} color="#f5f2e9" radius={.12} /><Soft at={[1.88, .74, .62]} size={[.56, .63, .2]} color="#eeeee6" radius={.05} /><Box at={[3, .6, .62]} size={[.7, .7, .48]} color="#bead90" /><Cylinder at={[3, 1.09, .62]} radius={.18} height={.07} color="#d5e0d8" />
  </>;
  return <><Box at={[5.4, .6, 3.98]} size={[2.4, .8, .52]} color="#d4d8cb" /><Box at={[5.4, 1.05, 3.98]} size={[2.5, .09, .6]} color="#bba98b" /><Box at={[6.5, .98, 1]} size={[.62, 1.6, .68]} color="#d0d8cc" /></>;
}

function Wall({ at, length, vertical = false, window = false, exterior = false, door = true }: { at: Point; length: number; vertical?: boolean; window?: boolean; exterior?: boolean; door?: boolean }) {
  const height = exterior ? 1.7 : 1.15, gap = window ? Math.min(2, length * .5) : 1.05, side = (length - gap) / 2;
  return <group position={at} rotation={[0, vertical ? Math.PI / 2 : 0, 0]}>
    {[-1, 1].map((sign) => <group key={sign}><Box at={[sign * (gap / 2 + side / 2), height / 2 + .17, 0]} size={[side, height, .14]} color={WALL} /><Box at={[sign * (gap / 2 + side / 2), height + .18, 0]} size={[side + .02, .055, .17]} color="#fffdf4" /><Box at={[sign * (gap / 2 + side / 2), .22, .075]} size={[side, .1, .025]} color="#ded9cc" /></group>)}
    {window ? <>
      <Box at={[0, .49, 0]} size={[gap, .64, .14]} color={WALL} /><Box at={[0, height + .08, 0]} size={[gap, .18, .14]} color={WALL} />
      <mesh position={[0, 1.2, 0]}><boxGeometry args={[gap, .95, .025]} /><meshPhysicalMaterial color="#a2c7c5" transparent opacity={.21} roughness={.1} depthWrite={false} /></mesh>
      {[.75, 1.65].map((y) => <Box key={y} at={[0, y, 0]} size={[gap, .045, .08]} color={FRAME} />)}
      {[-gap / 2, 0, gap / 2].map((x) => <Box key={x} at={[x, 1.35, 0]} size={[.035, .94, .08]} color={FRAME} />)}
      <Box at={[0, .72, 0]} size={[gap + .1, .055, .25]} color="#f8f5eb" />
    </> : <>
      {[-1, 1].map((sign) => <Box key={sign} at={[sign * (gap / 2 - .015), .82, 0]} size={[.065, 1.3, .18]} color="#d9d0be" />)}
      <Box at={[0, 1.48, 0]} size={[gap + .04, .065, .18]} color="#d9d0be" />
      {door && <group position={[-gap / 2, .18, 0]} rotation={[0, -.85, 0]}><Box at={[gap / 2, .63, 0]} size={[gap - .08, 1.25, .055]} color="#c2aa88" /><Box at={[gap - .18, .67, -.06]} size={[.11, .03, .05]} color="#68746f" /></group>}
    </>}
  </group>;
}

function House() {
  return <>
    <Soft at={[0, -.14, 0]} size={[17.3, .3, 12.05]} color="#dfe1d5" radius={.12} />
    <Box at={[0, -.02, 0]} size={[16.7, .055, 11.5]} color="#6b8152" />
    <Box at={[0, .04, 0]} size={[15.25, .08, 10.1]} color="#d8d5c9" />
    <Box at={[0, .1, 0]} size={[14.3, .12, 9.1]} color="#f1eee4" />
    {ROOMS.map((r) => {
      const p = world(r.x + r.w / 2, r.y + r.h / 2), width = r.w / 65, depth = r.h / 65;
      return <group key={r.id}>
        <Floor room={r} />
        <Wall at={[p[0], 0, p[2] - depth / 2]} length={width} exterior={r.y === 30} window={r.y === 30} door={r.id === "bathroom" || r.id === "garage"} />
        <Wall at={[p[0] - width / 2, 0, p[2]]} length={depth} vertical exterior={r.x === 30} window={r.x === 30} door={r.id === "bedroom" || r.id === "bathroom"} />
        <Html position={world(r.x + r.w / 2, r.y + 35, 2.15)} center style={{ pointerEvents: "none" }}><span className="room3d-label">{r.name}</span></Html>
        <Furniture room={r.id} />
      </group>;
    })}
    <Wall at={[7, 0, -2.15]} length={4.6} vertical exterior window /><Wall at={[7, 0, 2.3]} length={4.3} vertical exterior window />
    {/* Near walls are deliberately cut to sill height, retaining access to every placed device. */}
    <Box at={[0, .46, 4.47]} size={[14.1, .58, .14]} color={WALL} /><Box at={[0, .77, 4.47]} size={[14.13, .045, .19]} color="#fffdf3" />
    {[-7.7, 7.7].flatMap((x) => [-4.7, -1.5, 1.7, 4.7].map((z) => <Plant key={`${x}${z}`} at={[x, .06, z]} scale={.9} />))}
    {[-5.5, -2.5, .5, 3.5, 6.3].map((x) => <Plant key={x} at={[x, .06, -5.35]} scale={.8} />)}
    {[-.5, .5].map((x) => <Box key={x} at={[x - 4.5, .07, 5.1]} size={[.85, .04, .7]} color="#e8e3d5" />)}
  </>;
}

function DeviceModel({ type, live }: { type: DeviceType; live?: Live }) {
  const known = !!live?.reading, classes = known ? live!.classes : [];
  const active = classes.includes("dv-on"), motion = classes.includes("dv-motion"), open = classes.includes("dv-open");
  const alarm = classes.includes("dv-alarm"), recording = classes.includes("dv-rec");
  const body = known ? "#d5e3e3" : "#7a8995", dark = "#243b49";
  switch (type) {
    case "light": return <><Cylinder at={[0, 0.35, 0]} radius={0.13} height={0.5} color={body} /><mesh position={[0, 0.71, 0]}><sphereGeometry args={[0.3, 16, 12]} /><meshStandardMaterial color={active ? "#ffe3a4" : body} emissive={active ? "#ffc975" : "#000000"} emissiveIntensity={active ? 1.2 : 0} /></mesh></>;
    case "motion": return <><Box at={[0, 0.4, 0]} size={[0.48, 0.6, 0.22]} color={body} /><mesh position={[0, 0.48, 0.16]}><sphereGeometry args={[0.19, 12, 8]} /><meshStandardMaterial color={motion ? "#77ead3" : "#afc5cc"} emissive={motion ? "#42bd9b" : "#000000"} /></mesh></>;
    case "climate": return <><Box at={[0, 0.39, 0]} size={[0.4, 0.58, 0.24]} color={known ? "#75cbd5" : body} />{[-0.14, -0.04, 0.06, 0.16].map((y) => <Box key={y} at={[0, 0.42 + y, 0.13]} size={[0.26, 0.035, 0.025]} color={dark} />)}</>;
    case "door": return <><Box at={[0, 0.51, 0]} size={[0.6, 0.9, 0.12]} color={dark} /><group position={[-0.27, 0.1, 0]} rotation={[0, open ? -0.8 : 0, 0]}><Box at={[0.27, 0.43, 0.08]} size={[0.48, 0.8, 0.09]} color={body} /><Cylinder at={[0.44, 0.45, 0.18]} radius={0.045} height={0.05} color="#d5ba7b" /></group></>;
    case "lock": return <><mesh position={[0, 0.65, 0]}><torusGeometry args={[0.2, 0.07, 8, 18, Math.PI]} /><meshStandardMaterial color={body} /></mesh><group rotation={[0, open ? -0.6 : 0, 0]}><Box at={[0, 0.37, 0]} size={[0.54, 0.43, 0.28]} color={open ? "#79b7aa" : body} /><Box at={[0, 0.38, 0.16]} size={[0.07, 0.14, 0.025]} color={dark} /></group></>;
    case "camera": return <><Cylinder at={[0, 0.25, 0]} radius={0.1} height={0.3} color={body} /><Box at={[0, 0.52, 0]} size={[0.55, 0.32, 0.4]} color={body} /><mesh position={[0, 0.52, 0.25]} rotation={[Math.PI / 2, 0, 0]}><cylinderGeometry args={[0.16, 0.16, 0.12, 16]} /><meshStandardMaterial color={recording ? "#6cdcc1" : dark} /></mesh></>;
    case "plug": return <><Box at={[0, 0.36, 0]} size={[0.52, 0.52, 0.3]} color={body} />{[-0.12, 0.12].map((x) => <Box key={x} at={[x, 0.4, 0.16]} size={[0.045, 0.13, 0.025]} color={dark} />)}<Box at={[0, 0.2, 0.17]} size={[0.16, 0.035, 0.02]} color={active ? "#6ce8bf" : dark} emissive={active ? "#6ce8bf" : undefined} /></>;
    case "thermostat": return <><mesh position={[0, 0.43, 0]} rotation={[Math.PI / 2, 0, 0]}><cylinderGeometry args={[0.34, 0.34, 0.18, 24]} /><meshStandardMaterial color={body} /></mesh><Box at={[0, 0.44, 0.11]} size={[0.38, 0.25, 0.035]} color={classes.includes("dv-heat") ? "#c98164" : classes.includes("dv-cool") ? "#5a9dbe" : dark} /></>;
    case "smoke": return <><Cylinder at={[0, 0.31, 0]} radius={0.36} height={0.23} color={body} />{[-0.18, -0.06, 0.06, 0.18].map((x) => <Box key={x} at={[x, 0.43, 0]} size={[0.035, 0.02, 0.28]} color={dark} />)}<Cylinder at={[0, 0.46, 0.23]} radius={0.06} height={0.04} color={alarm ? "#ffb36c" : known ? "#72c5b0" : "#738295"} glow={alarm} /></>;
  }
}

function Scene({ props, focus, reset }: { props: Home3DProps; focus: string; reset: number }) {
  const { camera, gl, invalidate } = useThree();
  const controls = useRef<OrbitImpl>(null);
  const travel = useRef<{position: Vector3; target: Vector3} | null>(null);
  useFrame((_, dt) => {
    const goal = travel.current;
    if (!goal || !controls.current) return;
    const weight = 1 - Math.exp(-9 * Math.min(dt, .1));
    camera.position.lerp(goal.position, weight); controls.current.target.lerp(goal.target, weight);
    controls.current.update();
    if (camera.position.distanceTo(goal.position) < .01) travel.current = null;
    else invalidate();
  });
  const drag = useRef<{ id: string; x: number; y: number } | null>(null);
  const [preview, setPreview] = useState<{ x: number; y: number; valid: boolean } | null>(null);
  const [dragging, setDragging] = useState(false);
  const [hovered, setHovered] = useState<string | null>(null);
  const ray = useRef(new Raycaster()), plane = useRef(new Plane(new Vector3(0, 1, 0), -0.16));
  const current = useRef(props); current.current = props;
  const fromClient = (x: number, y: number) => {
    const rect = gl.domElement.getBoundingClientRect();
    if (x < rect.left || x > rect.right || y < rect.top || y > rect.bottom) return null;
    ray.current.setFromCamera(new Vector2((x - rect.left) / rect.width * 2 - 1, -(y - rect.top) / rect.height * 2 + 1), camera);
    const hit = ray.current.ray.intersectPlane(plane.current, new Vector3());
    return hit ? plan(hit) : null;
  };
  useEffect(() => {
    const r = ROOMS.find((r) => r.id === focus);
    const target = r ? world(r.x + r.w / 2, r.y + r.h / 2) : [0, 0, 0] as Point;
    const position = new Vector3(target[0] + (r ? 6 : CAMERA[0]), r ? 10 : CAMERA[1], target[2] + (r ? 9 : CAMERA[2]));
    if (matchMedia("(prefers-reduced-motion: reduce)").matches) {
      camera.position.copy(position); controls.current?.target.set(...target); controls.current?.update();
      travel.current = null;
    } else travel.current = { position, target: new Vector3(...target) };
    invalidate();
  }, [focus, reset, camera, invalidate]);
  useEffect(() => {
    const move = (e: PointerEvent) => {
      const p = current.current, id = drag.current?.id;
      if (!id && !p.placementType) return;
      const point = fromClient(e.clientX, e.clientY), spot = point ? place(p.devices, point.x, point.y, id) : null;
      setPreview(point ? { ...(spot ?? point), valid: !!spot } : null);
    };
    const up = (e: PointerEvent) => {
      const p = current.current, held = drag.current;
      if (!held && !p.placementType) return;
      const point = fromClient(e.clientX, e.clientY), spot = point ? place(p.devices, point.x, point.y, held?.id) : null;
      if (spot) {
        if (held && Math.hypot(e.clientX - held.x, e.clientY - held.y) > 5) p.onChange?.(p.devices.map((d) => d.id === held.id ? { ...d, ...spot } : d));
        else if (!held && p.placementType) p.onPlace?.(p.placementType, spot.x, spot.y);
      }
      drag.current = null; setDragging(false); setPreview(null);
    };
    const cancel = () => { drag.current = null; setDragging(false); setPreview(null); };
    window.addEventListener("pointermove", move); window.addEventListener("pointerup", up); window.addEventListener("pointercancel", cancel); window.addEventListener("blur", cancel);
    return () => { window.removeEventListener("pointermove", move); window.removeEventListener("pointerup", up); window.removeEventListener("pointercancel", cancel); window.removeEventListener("blur", cancel); };
  }, [camera, gl]);
  const begin = (e: ThreeEvent<PointerEvent>, d: PlacedDevice) => {
    if (!props.onChange || e.button !== 0) return;
    e.stopPropagation(); props.onSelect?.(d.id);
    drag.current = { id: d.id, x: e.clientX, y: e.clientY }; setDragging(true);
  };
  return <>
    <color attach="background" args={["#e5e9e4"]} />
    <ambientLight intensity={.75} />
    <hemisphereLight args={["#fff8e8", "#909b87", 1.1]} />
    <directionalLight position={[-6, 16, 4]} intensity={2.4} color="#fff6e2" castShadow shadow-radius={3} shadow-mapSize={[2048, 2048]} shadow-camera-left={-12} shadow-camera-right={12} shadow-camera-top={12} shadow-camera-bottom={-12} shadow-bias={-0.001} />
    <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.39, 0]} receiveShadow><planeGeometry args={[200, 200]} /><meshStandardMaterial color="#e5e9e4" roughness={.95} /></mesh>
    <House />
    {props.devices.map((d) => {
      const l = props.live.get(d.id), color = COLORS[l?.state ?? "idle"], pos = world(d.x, d.y, 0.18), chosen = props.selected === d.id;
      return <group key={d.id} position={pos} onPointerDown={(e) => begin(e, d)} onPointerOver={(e) => { e.stopPropagation(); setHovered(d.id); gl.domElement.style.cursor = "grab"; }} onPointerOut={() => { setHovered(null); gl.domElement.style.cursor = "auto"; }} onClick={(e) => { e.stopPropagation(); props.onSelect?.(d.id); }}>
        <Cylinder at={[0, 0.035, 0]} radius={chosen ? 0.38 : 0.28} height={0.035} color={chosen ? "#7de8f4" : color} glow={chosen} />
        <group scale={.7}><DeviceModel type={d.type} live={l} /></group>
        {(chosen || hovered === d.id) ? <Html position={[0, 1.5, 0]} center style={{ pointerEvents: "none" }} zIndexRange={[30, 25]}><div className={`device3d-label ${chosen ? "chosen" : ""}`}><b>{d.name}</b><span>{l?.reading ?? (l?.state === "offline" ? "Disconnected" : "Waiting for telemetry")}</span>{d.type === "thermostat" && l?.reading && Number.isFinite(l.device?.state?.target) && <span>{l.device!.state!.target} °C target</span>}<small>{d.source === "wokwi" ? d.controller ? CONTROLLERS[d.controller].label : "Wokwi · shared bridge" : "Software simulation"}</small></div></Html>
          : <Html position={[0.3, 0.18, 0]} center style={{ pointerEvents: "none" }} zIndexRange={[10, 0]}><span className={`device3d-backing ${d.source}`} aria-hidden="true">{d.source === "wokwi" ? "W" : "S"}</span></Html>}
      </group>;
    })}
    {props.devices.filter((d) => (props.live.get(d.id)?.msgs ?? 0) > 0).map((d) => <Line key={`link-${d.id}`} points={[world(d.x, d.y, 0.22), world(HUB.x, HUB.y, 0.22)]} color={COLORS[props.live.get(d.id)?.state ?? "quiet"]} lineWidth={1} transparent opacity={0.3} dashed dashSize={0.12} gapSize={0.1} />)}
    <group position={world(HUB.x, HUB.y, 0.2)}>
      <Box at={[0, 0.26, 0]} size={[0.95, 0.35, 0.62]} color="#b7d3da" />
      {[-0.35, 0.35].map((x) => <Cylinder key={x} at={[x, 0.64, 0]} radius={0.025} height={0.7} color="#a7c7ce" />)}
      <Box at={[0, 0.29, 0.32]} size={[0.52, 0.04, 0.02]} color="#55d8bf" />
      <Html position={[0, 1.0, 0]} center style={{ pointerEvents: "none" }}><span className="hub3d-label">MQTT HUB</span></Html>
    </group>
    <group position={world(HUB.x + 45, HUB.y + 85, 0.22)}>
      <Box at={[0, 0.5, 0]} size={[0.85, 0.55, 0.12]} color="#8daab7" />
      <Box at={[0, 0.5, 0.075]} size={[0.72, 0.42, 0.025]} color="#214352" />
      <Cylinder at={[0, 0.18, 0]} radius={0.055} height={0.18} color="#9aafb8" />
      <Box at={[0, 0.07, 0]} size={[0.55, 0.05, 0.32]} color="#809ba7" />
      <Html position={[0, 0.9, 0]} center style={{ pointerEvents: "none" }}><span className="hub3d-label observer3d-label">EDGE WATCH<small>Passive observer</small></span></Html>
    </group>
    <Line points={[world(HUB.x, HUB.y, 0.24), world(HUB.x + 45, HUB.y + 85, 0.24)]} color="#6a9fb6" lineWidth={1} dashed dashSize={0.08} gapSize={0.12} transparent opacity={0.5} />
    {props.attacker && <>
      <group position={world(ATTACKER.x, ATTACKER.y, 0.2)}>
        <Box at={[0, 0.23, 0]} size={[0.9, 0.12, 0.65]} color="#344252" />
        <Box at={[0, 0.65, -0.18]} size={[0.9, 0.7, 0.12]} color={props.attacker.state === "alert" ? "#d3657b" : "#bb985f"} />
        <Html position={[0, 1.45, 0]} center style={{ pointerEvents: "none" }}><span className="attacker3d-label">Lab attack source<small>{props.attacker.outcome === "missed" ? "Not detected in this run" : props.attacker.state === "alert" ? "IDS alert raised" : props.attacker.active ? "Attack started · observing traffic" : "Processing final traffic windows"}</small>{typeof props.attacker.delay === "number" && Number.isFinite(props.attacker.delay) && <small>Detection delay: {props.attacker.delay.toFixed(1)} s</small>}<small>{props.attacker.msgs > 0 ? `${props.attacker.msgs.toFixed(0)} measured messages/s` : "No recent measured traffic"}</small></span></Html>
      </group>
      {props.attacker.msgs > 0 && <Line points={[world(ATTACKER.x, ATTACKER.y, 0.42), world(HUB.x, HUB.y, 0.42)]} color={props.attacker.state === "alert" ? "#ff657c" : "#e2b969"} lineWidth={2} dashed dashSize={0.2} gapSize={0.12} />}
    </>}
    {preview && <mesh position={world(preview.x, preview.y, 0.23)} rotation={[-Math.PI / 2, 0, 0]}><ringGeometry args={[0.38, 0.53, 24]} /><meshBasicMaterial color={preview.valid ? "#7bedcf" : "#ff657c"} transparent opacity={0.9} /></mesh>}
    <OrbitControls ref={controls} makeDefault enabled={!dragging && !props.placementType} enableDamping={false} minDistance={7} maxDistance={30} minPolarAngle={0.18} maxPolarAngle={1.0} target={[0, 0, 0]} onChange={() => {
      const c = controls.current; if (!c) return;
      const before = c.target.clone(); c.target.clamp(new Vector3(-7, 0, -4.5), new Vector3(7, 0, 4.5));
      camera.position.add(c.target.clone().sub(before));
    }} />
  </>;
}
export default function Home3D(props: Home3DProps) {
  const [focus, setFocus] = useState("all"), [reset, setReset] = useState(0), [failed, setFailed] = useState(false);
  const [visible, setVisible] = useState(!document.hidden);
  useEffect(() => { const change = () => setVisible(!document.hidden); document.addEventListener("visibilitychange", change); return () => document.removeEventListener("visibilitychange", change); }, []);
  if (failed) return <div className="scene-fallback"><p role="status">The 3D view is unavailable. Your device controls are ready below.</p>{props.fallback}</div>;
  return <SceneBoundary fallback={props.fallback}>
    <div className="home3d-shell">
      <div className="scene3d-toolbar"><span className="scene3d-title"><i />INTERACTIVE HOME <small>Live device state</small></span><div><label>View <select aria-label="Focus room" value={focus} onChange={(e) => setFocus(e.target.value)}><option value="all">Whole home</option>{ROOMS.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}</select></label><button className="btn btn-sm" onClick={() => { setFocus("all"); setReset((n) => n + 1); }}>Reset camera</button></div></div>
      <div className={`scene3d-stage ${props.placementType ? "placing" : ""}`} aria-label="Interactive 3D home. Device list and controls are available below.">
        <Canvas shadows dpr={[1, 1.5]} frameloop={visible ? "demand" : "never"} camera={{ position: CAMERA, fov: 36, near: 0.1, far: 100 }} gl={{ antialias: true, powerPreference: "low-power" }} fallback={<div className="scene-fallback">{props.fallback}</div>} onCreated={({ gl }) => gl.domElement.addEventListener("webglcontextlost", (e) => { e.preventDefault(); setFailed(true); }, { once: true })}>
          <Scene props={props} focus={focus} reset={reset} />
        </Canvas>
        <div className="scene3d-instructions">{props.placementType ? `Drop ${TYPES[props.placementType].label.toLowerCase()} onto a room · green ring = valid placement` : "Drag to orbit · scroll to zoom · select a device for details · W: Wokwi · S: software"}</div>
      </div>
      {props.deviceList !== false && <details className="scene3d-device-list"><summary onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); const details = e.currentTarget.parentElement as HTMLDetailsElement; details.open = !details.open; } }}>Device list & controls · {props.devices.length} placed</summary>{props.fallback}</details>}
    </div>
  </SceneBoundary>;
}
