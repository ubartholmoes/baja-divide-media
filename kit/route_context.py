#!/usr/bin/env python3
"""Route context for a Baja Divide position: Ulrich's GPX (Tecate -> San José del Cabo, 2,489 km)
+ Baja Divide Route Guide (Pat Boyle, 2026 update), sections 2-18 mapped onto the track km.
Usage: route_context.py --km 450 [--day 4]  -> facts for the caption (use selectively, never invent beyond them)."""
import argparse, json, os
D = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "route_data.json"), encoding="utf-8"))
ap = argparse.ArgumentParser(); ap.add_argument("--km", type=float, required=True); ap.add_argument("--day", type=int)
a = ap.parse_args(); K = max(0, min(D["route_km"], a.km)); step = D["profile_step_km"]
def at(arr, k):
    i = min(int(k // step), len(arr) - 2); f = (k - i * step) / step
    return arr[i] + (arr[i + 1] - arr[i]) * f
places = D["places"]
prev = [p for p in places if p["km"] <= K + 3]; nxt = [p for p in places if p["km"] > K + 3]
region = next((r["name"] for r in D["regions"] if r["from"] <= K < r["to"]), D["regions"][-1]["name"])
climb = D["climb_cum_m"]; ele = D["elevation_m"]
ahead = [x * step for x in range(int(K // step), min(len(ele), int((K + 100) // step) + 1))]
hi_k = max(ahead, key=lambda k: ele[int(k // step)]) if ahead else K
def n(x): return f"{x:,.0f}".replace(",", ".")
def fmt(p, d):
    s = p["name"] + (" (Umgebung)" if p.get("near") else "")
    return s + (f" – {p['note']}" if p["note"] else "") + f" [{d:.0f} km]"
print(f"Position: km {K:.0f} von {D['route_km']} ({K / D['route_km'] * 100:.0f} %)" + (f", Tag {a.day}" if a.day else ""))
print(f"Gegend: {region}")
print(f"Höhe hier: ~{at(ele, K):.0f} m")
if prev:
    p = prev[-1]; d = K - p["km"]
    print(("Gerade bei/in: " if abs(d) <= 3 else "Zuletzt passiert: ") + fmt(p, abs(d)) + ("" if abs(d) <= 3 else " zurück"))
if nxt:
    print("Als Nächstes: " + "; ".join(fmt(p, p["km"] - K) for p in nxt[:3]))
print(f"Höhenmeter bisher: ~{n(at(climb, K))} m, noch: ~{n(climb[-1] - at(climb, K))} m")
print(f"Nächste 100 km: ~{n(at(climb, min(K + 100, D['route_km'])) - at(climb, K))} Hm, höchster Punkt ~{ele[int(hi_k // step)]} m bei km {hi_k:.0f}")
print(f"Bis zum Ziel: {D['route_km'] - K:.0f} km")
sec = next((x for x in D["sections"] if x["from"] <= K < x["to"]), D["sections"][-1])
L = sec["to"] - sec["from"]
print(f"\nGuide-Abschnitt {sec['n']}: {sec['title']} (km {sec['from']}–{sec['to']}, {L} km; {K - sec['from']:.0f} km drin, {sec['to'] - K:.0f} km bis Abschnittsende)")
for h in sec["highlights"]: print(f"  • {h}")
print(f"  Versorgung: {sec['supply']}")
nx = next((x for x in D["sections"] if x["from"] >= sec["to"]), None)
if nx and sec["to"] - K < 60:
    print(f"Danach Abschnitt {nx['n']}: {nx['title']} – {nx['highlights'][0]}")
