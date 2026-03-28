#!/usr/bin/env python3
"""
GwadaBot — Analyse OSM Guadeloupe
Évalue l'état de la carte avant de lancer l'import.
Découpe la Guadeloupe en 4 zones pour éviter les timeouts Overpass.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import overpy

# ── Zones ──────────────────────────────────────────
ZONES = [
    {"name": "Grande-Terre Nord", "bb": "16.25,-61.61,16.52,-60.99"},
    {"name": "Grande-Terre Sud", "bb": "15.98,-61.65,16.25,-61.00"},
    {"name": "Basse-Terre Nord", "bb": "16.10,-61.85,16.45,-61.55"},
    {"name": "Basse-Terre Sud", "bb": "15.83,-61.85,16.10,-61.55"},
]

OLD_THRESHOLD_YEAR = 2015
MAX_RETRIES = 4

LOG_DIR = Path(__file__).resolve().parent.parent / "logs"


def _query_retry(api: overpy.Overpass, query: str, zone: str):
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return api.query(query)
        except overpy.exception.OverpassGatewayTimeout:
            wait = 15 * attempt
            print(f"   [timeout] {zone} — tentative {attempt}/{MAX_RETRIES}, attente {wait}s…")
            time.sleep(wait)
        except Exception as exc:
            wait = 10 * attempt
            print(f"   [erreur]  {zone} — {type(exc).__name__}, attente {wait}s…")
            time.sleep(wait)
    print(f"   [echec]   {zone} — abandonnée après {MAX_RETRIES} tentatives")
    return None


def _analyze_zone(api: overpy.Overpass, zone: dict) -> dict:
    query = f'[out:json][timeout:90];way({zone["bb"]})[highway];out ids meta;'
    result = _query_retry(api, query, zone["name"])
    if not result:
        return {"total": 0, "old": 0, "very_old": 0, "by_year": {}}

    total = old = very_old = 0
    by_year: dict[int, int] = {}

    for way in result.ways:
        ts = way.attributes.get("timestamp", "")
        total += 1
        if ts:
            try:
                year = int(str(ts)[:4])
                by_year[year] = by_year.get(year, 0) + 1
                if year <= OLD_THRESHOLD_YEAR:
                    old += 1
                if year <= 2012:
                    very_old += 1
            except ValueError:
                pass

    return {"total": total, "old": old, "very_old": very_old, "by_year": by_year}


def analyze_osm_guadeloupe() -> dict:
    print("GwadaBot — Analyse OSM Guadeloupe")
    print("=" * 55)

    api = overpy.Overpass(url="https://overpass-api.de/api/interpreter")

    roads_total = roads_old = roads_vold = 0
    all_years: dict[int, int] = {}
    zone_results = []

    for i, zone in enumerate(ZONES, 1):
        print(f"\n  Zone {i}/4 — {zone['name']}…")
        age = _analyze_zone(api, zone)

        roads_total += age["total"]
        roads_old += age["old"]
        roads_vold += age["very_old"]
        for y, c in age["by_year"].items():
            all_years[y] = all_years.get(y, 0) + c

        pct = age["old"] / max(age["total"], 1) * 100
        print(f"   Routes: {age['total']:,} | avant 2015: {pct:.0f}%")
        zone_results.append({"zone": zone["name"], "roads_total": age["total"], "roads_old_pct": round(pct, 1)})

        if i < len(ZONES):
            time.sleep(3)

    # ── Résumé ─────────────────────────────────────
    pct_total = roads_old / max(roads_total, 1) * 100
    print("\n" + "=" * 55)
    print("RESULTATS — GUADELOUPE COMPLETE")
    print("=" * 55)
    print(f"\n  Routes total:    {roads_total:,}")
    print(f"  Avant 2015:      {roads_old:,} ({pct_total:.1f}%)")
    print(f"  Avant 2013:      {roads_vold:,}")

    print("\n  Répartition par année:")
    scale = max(roads_total // 400, 1)
    for year in sorted(all_years):
        cnt = all_years[year]
        bar = "#" * min(cnt // scale, 40)
        marker = " !" if year <= 2012 else ""
        print(f"    {year}: {bar} {cnt:,}{marker}")

    # ── Recommandations ────────────────────────────
    print("\n" + "=" * 55)
    print("RECOMMANDATIONS")
    print("=" * 55)
    if pct_total > 50:
        print(f"\n  [HAUT] Routes ({pct_total:.0f}% avant 2015)")
    elif pct_total > 25:
        print(f"\n  [MOY]  Routes ({pct_total:.0f}% avant 2015)")
    else:
        print(f"\n  [OK]   Routes relativement a jour ({pct_total:.0f}%)")
    print("  [MOY]  Batiments — BD TOPO plus complete qu'OSM")
    print("  [OK]   Hydrographie — ravines souvent absentes")

    # ── Rapport JSON ───────────────────────────────
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "roads": {
            "total": roads_total,
            "old_before_2015": roads_old,
            "old_pct": round(pct_total, 1),
            "very_old_before_2013": roads_vold,
            "by_year": {str(k): v for k, v in sorted(all_years.items())},
        },
        "zones": zone_results,
    }

    LOG_DIR.mkdir(exist_ok=True)
    report_path = LOG_DIR / "osm_analysis_guadeloupe.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n  Rapport: {report_path}")
    print("\n  Analyse terminee.\n")
    return report


if __name__ == "__main__":
    analyze_osm_guadeloupe()
