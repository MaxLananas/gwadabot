#!/usr/bin/env python3
"""
GwadaBot — Moteur de Conflation IGN ↔ OSM
Sous-zones parallèles + STRtree.
"""
from __future__ import annotations

import logging
import math
import time
from dataclasses import dataclass, field
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

import overpy
from shapely.geometry import Point
from shapely.strtree import STRtree

log = logging.getLogger("gwadabot.conflation")

THRESHOLD_SKIP_M = 10.0
THRESHOLD_UPDATE_M = 50.0
MAX_RETRIES = 3

IGN_PRIORITY = frozenset({
    "highway", "waterway", "building", "surface", "maxspeed",
    "bridge", "tunnel", "layer", "height", "building:levels",
    "man_made", "oneway", "ref", "width", "lanes",
    "leisure", "landuse", "natural", "aeroway", "power",
})
OSM_PRIORITY = frozenset({
    "name", "name:fr", "name:gcf", "alt_name",
    "wikipedia", "wikidata", "website", "phone",
    "opening_hours", "wheelchair", "description",
})


@dataclass
class ConflationResult:
    action: str
    osm_id: Optional[int] = None
    distance_m: float = float("inf")
    reason: str = ""
    merged_tags: dict = field(default_factory=dict)


def haversine(lat1, lon1, lat2, lon2) -> float:
    R = 6_371_000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def merge_tags(ign_tags: dict, osm_tags: dict) -> tuple[dict, dict]:
    merged = dict(osm_tags)
    changes = {}
    for key, val in ign_tags.items():
        if not val or str(val) in ("", "None", "nan"):
            continue
        if key in OSM_PRIORITY:
            if key not in osm_tags or not osm_tags[key]:
                merged[key] = val
                changes[key] = {"old": osm_tags.get(key), "new": val}
        elif key in IGN_PRIORITY:
            if osm_tags.get(key) != val:
                merged[key] = val
                changes[key] = {"old": osm_tags.get(key), "new": val}
        else:
            if key not in osm_tags:
                merged[key] = val
                changes[key] = {"old": None, "new": val}
    return merged, changes


class ConflationEngine:
    def __init__(self, items: list[dict] | None = None):
        self._items: list[dict] = items or []
        self._geoms = [it["point"] for it in self._items]
        self._tree = STRtree(self._geoms) if self._geoms else None

    @classmethod
    def from_overpass(cls, elements: list) -> ConflationEngine:
        pts = []
        for el in elements:
            try:
                if hasattr(el, "lat") and hasattr(el, "lon"):
                    pts.append({
                        "point": Point(float(el.lon), float(el.lat)),
                        "tags": dict(el.tags) if el.tags else {},
                        "id": int(el.id),
                    })
            except Exception:
                continue
        log.info(f"  ConflationEngine : {len(pts):,} elements indexes")
        return cls(pts)

    @property
    def count(self) -> int:
        return len(self._items)

    def find_match(self, ign_geom, ign_tags: dict) -> ConflationResult:
        if not self._tree or not self._items:
            return ConflationResult("create", reason="no_index")

        if ign_geom.geom_type == "Point":
            ref = ign_geom
        elif ign_geom.geom_type in ("LineString", "MultiLineString"):
            ref = ign_geom.interpolate(0.5, normalized=True)
        elif ign_geom.geom_type in ("Polygon", "MultiPolygon"):
            ref = ign_geom.centroid
        else:
            return ConflationResult("create", reason="unsupported")

        idx = self._tree.nearest(ref)
        item = self._items[idx]
        pt = item["point"]
        dist = haversine(ref.y, ref.x, pt.y, pt.x)

        if dist > THRESHOLD_UPDATE_M:
            return ConflationResult("create", distance_m=dist, reason="far")

        merged, changes = merge_tags(ign_tags, item["tags"])
        if dist <= THRESHOLD_SKIP_M:
            if changes:
                return ConflationResult("update", item["id"], dist, "tag_update", merged)
            return ConflationResult("skip", item["id"], dist, "identical")
        return ConflationResult("update", item["id"], dist, f"moved_{dist:.0f}m", merged)


def _subdivide_bbox(bbox: dict, grid: int = 4) -> list[dict]:
    lat_step = (bbox["max_lat"] - bbox["min_lat"]) / grid
    lon_step = (bbox["max_lon"] - bbox["min_lon"]) / grid
    zones = []
    for i in range(grid):
        for j in range(grid):
            zones.append({
                "min_lat": round(bbox["min_lat"] + i * lat_step, 5),
                "max_lat": round(bbox["min_lat"] + (i + 1) * lat_step, 5),
                "min_lon": round(bbox["min_lon"] + j * lon_step, 5),
                "max_lon": round(bbox["min_lon"] + (j + 1) * lon_step, 5),
            })
    return zones


def _fetch_zone(zone: dict, zone_idx: int, tag_filter: str = "") -> list:
    api = overpy.Overpass(url="https://overpass-api.de/api/interpreter")
    bb = f"{zone['min_lat']},{zone['min_lon']},{zone['max_lat']},{zone['max_lon']}"
    query = f"""[out:json][timeout:45];(node({bb}){tag_filter};way({bb}){tag_filter};);out body;>;out skel qt;"""

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            result = api.query(query)
            return list(result.nodes)
        except Exception as exc:
            wait = 5 * attempt
            log.debug(f"  Zone {zone_idx} attempt {attempt}: {type(exc).__name__}")
            time.sleep(wait)
    log.warning(f"  Zone {zone_idx} failed")
    return []


def load_osm_parallel(bbox: dict, tag_filter: str = "[building]",
                      grid: int = 4, workers: int = 4) -> list:
    zones = _subdivide_bbox(bbox, grid)
    log.info(f"  Conflation : {len(zones)} zones, {workers} threads, filtre={tag_filter}")

    all_elements = []
    seen_ids = set()

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_fetch_zone, z, i, tag_filter): i for i, z in enumerate(zones)}
        done = 0
        for future in as_completed(futures):
            done += 1
            try:
                for el in future.result():
                    eid = getattr(el, "id", None)
                    if eid and eid not in seen_ids:
                        seen_ids.add(eid)
                        all_elements.append(el)
            except Exception as exc:
                log.warning(f"  Zone error: {exc}")
            if done % 4 == 0 or done == len(futures):
                log.info(f"  Overpass : {done}/{len(zones)} zones, {len(all_elements):,} el.")

    log.info(f"  Total : {len(all_elements):,} elements uniques")
    return all_elements
