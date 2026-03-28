#!/usr/bin/env python3
"""
 ██████╗ ██╗    ██╗ █████╗ ██████╗  █████╗ ██████╗  ██████╗ ████████╗
██╔════╝ ██║    ██║██╔══██╗██╔══██╗██╔══██╗██╔══██╗██╔═══██╗╚══██╔══╝
██║  ███╗██║ █╗ ██║███████║██║  ██║███████║██████╔╝██║   ██║   ██║
██║   ██║██║███╗██║██╔══██║██║  ██║██╔══██║██╔══██╗██║   ██║   ██║
╚██████╔╝╚███╔███╔╝██║  ██║██████╔╝██║  ██║██████╔╝╚██████╔╝   ██║
 ╚═════╝  ╚══╝╚══╝ ╚═╝  ╚═╝╚═════╝ ╚═╝  ╚═╝╚═════╝  ╚═════╝   ╚═╝

GwadaBot v2.1 — Import BD TOPO IGN -> OSM (Guadeloupe 971)
Intègre les retours communautaires (bibi, benoitdd — mars 2026).
"""
from __future__ import annotations
import os, sys, time, json, logging, argparse, re
import xml.sax.saxutils as saxutils
import multiprocessing as mp
from pathlib import Path
from datetime import datetime
from typing import Callable
from collections import Counter

from dotenv import load_dotenv
PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=PROJECT_ROOT / ".env")

import fiona, osmapi, numpy as np, geopandas as gpd
from shapely.geometry import LineString, MultiLineString, MultiPolygon, Point, Polygon
from shapely.ops import transform
from shapely.validation import make_valid
from requests_oauthlib import OAuth2Session

if sys.platform == "win32":
    for _s in (sys.stdout, sys.stderr):
        try: _s.reconfigure(encoding="utf-8", errors="replace")
        except AttributeError: pass

# ══════════════════════════════════════════════════
#  CONSTANTES
# ══════════════════════════════════════════════════
BBOX_GUADELOUPE = {"min_lat": 15.8326, "min_lon": -61.8097, "max_lat": 16.5144, "max_lon": -60.9971}
BATCH_SIZE = 500
DELAY_BETWEEN_BATCHES = 2
MAX_PER_DAY = 50_000
DRY_RUN_SAMPLE_BATCHES = 3
NUM_WORKERS = min(mp.cpu_count(), 8)

CHANGESET_TAGS = {
    "comment": "GwadaBot -- Import Guadeloupe depuis BD TOPO IGN",
    "source": "IGN BD TOPO -- Licence Ouverte Etalab 2.0",
    "bot": "yes", "import": "yes",
    "created_by": "GwadaBot/2.1",
    "url": "https://wiki.openstreetmap.org/wiki/Import/GwadaBot",
}

# ── Mappings (intègre retours bibi + benoitdd) ────

# BATI : Religieux retiré du map — traité à part dans le convertisseur
USAGE1_BATI_MAP = {
    "Résidentiel": "residential",
    "Annexe": "yes",
    "Agricole": "farm",
    "Commercial et services": "commercial",
    "Industriel": "industrial",
    "Sportif": "sports",
    "Indifférencié": "yes",
}
NATURE_BATI_MAP = {
    "Bâtiment indifférencié": {"building": "yes"},
    "Bâtiment industriel": {"building": "industrial"},
    "Bâtiment commercial": {"building": "commercial"},
    "Bâtiment agricole": {"building": "farm"},
    "Serre": {"building": "greenhouse"},
    "Réservoir": {"man_made": "storage_tank"},
    "Construction légère": {"building": "yes"},
    "Tribune": {"building": "grandstand"},
    "Chapelle": {"building": "chapel"},
    "Tour, donjon, moulin": {"building": "tower", "man_made": "tower"},
    "Fort, blockhaus, casemate": {"building": "bunker", "historic": "fort"},
}

# ROUTES : Bretelle=trunk_link, Route 2 chaussées=primary (retour bibi)
NATURE_ROUTE_MAP = {
    "Autoroute": {"highway": "motorway"},
    "Quasi-autoroute": {"highway": "trunk"},
    "Bretelle": {"highway": "trunk_link"},
    "Route à 2 chaussées": {"highway": "primary"},
    "Route à 1 chaussée": {"highway": "secondary"},
    "Route empierrée": {"highway": "unclassified", "surface": "unpaved"},
    "Chemin": {"highway": "track"},
    "Sentier": {"highway": "path"},
    "Piste cyclable": {"highway": "cycleway"},
    "Escalier": {"highway": "steps"},
    "Rond-point": {"junction": "roundabout"},
}

NATURE_HYDRO_MAP = {
    "Cours d'eau": {"waterway": "river"},
    "Canal": {"waterway": "canal"},
    "Fossé": {"waterway": "ditch"},
    "Ravine": {"waterway": "stream", "note": "ravine"},
    "Ruisseau": {"waterway": "stream"},
    "Delta": {"waterway": "river"},
}
NATURE_PLAN_EAU_MAP = {
    "Lac": {"natural": "water", "water": "lake"},
    "Retenue": {"natural": "water", "water": "reservoir"},
    "Réservoir": {"natural": "water", "water": "reservoir"},
    "Mare": {"natural": "water", "water": "pond"},
    "Lagune": {"natural": "water", "water": "lagoon"},
    "Mangrove": {"natural": "wetland", "wetland": "mangrove"},
}
NATURE_SPORT_MAP = {
    "Terrain de football": {"leisure": "pitch", "sport": "soccer"},
    "Terrain de rugby": {"leisure": "pitch", "sport": "rugby_union"},
    "Terrain de tennis": {"leisure": "pitch", "sport": "tennis"},
    "Terrain de basket-ball": {"leisure": "pitch", "sport": "basketball"},
    "Terrain de handball": {"leisure": "pitch", "sport": "handball"},
    "Terrain multisports": {"leisure": "pitch", "sport": "multi"},
    "Piscine": {"leisure": "swimming_pool"},
    "Terrain de pétanque": {"leisure": "pitch", "sport": "boules"},
    "Terrain de volley-ball": {"leisure": "pitch", "sport": "volleyball"},
    "Plateau d'éducation physique et sportive": {"leisure": "pitch"},
    "Pas de tir": {"leisure": "pitch", "sport": "shooting"},
    "Terrain de boules": {"leisure": "pitch", "sport": "boules"},
}

# VEGETATION : bananeraie = orchard+trees (pas crop), retour bibi
NATURE_VEGETATION_MAP = {
    "Forêt fermée de feuillus": {"natural": "wood", "leaf_type": "broadleaved"},
    "Forêt fermée de conifères": {"natural": "wood", "leaf_type": "needleleaved"},
    "Forêt fermée mixte": {"natural": "wood", "leaf_type": "mixed"},
    "Forêt ouverte": {"natural": "wood"},
    "Haie": {"natural": "tree_row"},
    "Lande ligneuse": {"natural": "heath"},
    "Verger": {"landuse": "orchard"},
    "Vigne": {"landuse": "vineyard"},
    "Bananeraie": {"landuse": "orchard", "trees": "banana_plants"},
    "Canne à sucre": {"landuse": "farmland", "crop": "sugarcane"},
    "Mangrove": {"natural": "wetland", "wetland": "mangrove"},
    "Bois": {"natural": "wood"},
    "Broussailles": {"natural": "scrub"},
    "Pépinière": {"landuse": "plant_nursery"},
    "Zone arborée": {"natural": "wood"},
    "Forêt fermée sans couvert arboré": {"natural": "wood"},
    # Lowercase pour BD TOPO v3.5
    "forêt fermée de feuillus": {"natural": "wood", "leaf_type": "broadleaved"},
    "mangrove": {"natural": "wetland", "wetland": "mangrove"},
    "bananeraie": {"landuse": "orchard", "trees": "banana_plants"},
    "canne à sucre": {"landuse": "farmland", "crop": "sugarcane"},
    "verger": {"landuse": "orchard"},
}
NATURE_EQUIP_MAP = {
    "Aérogare": {"aeroway": "terminal"},
    "Parking": {"amenity": "parking"},
    "Gare routière": {"amenity": "bus_station"},
    "Port": {"leisure": "marina"},
    "Gare maritime": {"amenity": "ferry_terminal"},
    "Péage": {"barrier": "toll_booth"},
    "Aire de repos ou de service": {"highway": "rest_area"},
    "Héliport": {"aeroway": "heliport"},
    "Tour de contrôle aérien": {"man_made": "tower", "tower:type": "aircraft_control"},
    "Gare voyageurs uniquement": {"railway": "station"},
    "Gare voyageurs et fret": {"railway": "station"},
    "Station de métro": {"railway": "station", "station": "subway"},
    "Arrêt voyageurs": {"highway": "bus_stop"},
    "Carrefour": {"highway": "junction"},
    "Rond-point": {"junction": "roundabout"},
}
NATURE_CONSTRUCTION_MAP = {
    "Barrage": {"waterway": "dam"},
    "Piscine": {"leisure": "swimming_pool"},
    "Pont": {"man_made": "bridge"},
    "Stade couvert": {"building": "stadium"},
    "Tribune": {"building": "grandstand"},
    "Dalle de protection": {"man_made": "bridge"},
    "Escalier": {"highway": "steps"},
    "Mur anti-bruit": {"barrier": "wall", "wall": "noise_barrier"},
    "Péage": {"barrier": "toll_booth"},
}
THEME_TAG_FILTER = {
    "BATI": "[building]", "TRANSPORT": "[highway]", "HYDROGRAPHIE": "[waterway]",
    "ADMINISTRATIF": "[boundary=administrative]", "SPORT": "[leisure]",
    "VEGETATION": "[natural]", "PLAN_EAU": "[natural=water]",
    "PYLONE": "[power=tower]", "LIGNE_ELEC": "[power=line]",
    "AERODROME": "[aeroway]", "RESERVOIR": "[man_made=reservoir]",
    "CIMETIERE": "[landuse=cemetery]", "EQUIPEMENT": "", "CONSTRUCTION": "",
}

# ══════════════════════════════════════════════════
#  LOGGING
# ══════════════════════════════════════════════════
LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)
_log_file = LOG_DIR / f"gwadabot_{datetime.now():%Y%m%d_%H%M%S}.log"
_fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
_fh = logging.FileHandler(_log_file, encoding="utf-8"); _fh.setLevel(logging.DEBUG); _fh.setFormatter(_fmt)
_sh = logging.StreamHandler(sys.stdout); _sh.setLevel(logging.INFO); _sh.setFormatter(_fmt)
log = logging.getLogger("gwadabot"); log.setLevel(logging.DEBUG)
log.addHandler(_fh); log.addHandler(_sh)

# ══════════════════════════════════════════════════
#  GÉOMÉTRIE
# ══════════════════════════════════════════════════
def _strip_z(x, y, z=None): return (x, y)

def strip_z_vectorized(gdf):
    gdf = gdf.copy()
    try:
        from shapely import force_2d
        gdf["geometry"] = force_2d(gdf["geometry"].values); return gdf
    except ImportError: pass
    geoms = gdf["geometry"].values
    has_z = np.array([g.has_z if g is not None else False for g in geoms])
    if has_z.any():
        for i in np.where(has_z)[0]: geoms[i] = transform(_strip_z, geoms[i])
        gdf["geometry"] = geoms
    return gdf

def validate_geometries(gdf):
    gdf = gdf.copy()
    try:
        from shapely import is_valid as sv_iv, make_valid as sv_mv, is_empty as sv_ie
        geoms = gdf["geometry"].values
        mask = ~sv_iv(geoms)
        if mask.sum() > 0:
            log.warning(f"  {mask.sum()} invalides -> make_valid()")
            geoms[mask] = sv_mv(geoms[mask]); gdf["geometry"] = geoms
        before = len(gdf)
        gdf = gdf[~sv_ie(gdf["geometry"].values) & gdf["geometry"].notna().values].copy()
    except ImportError:
        before = len(gdf)
        inv = np.array([not g.is_valid if g is not None else True for g in gdf["geometry"].values])
        if inv.any():
            geoms = gdf["geometry"].values
            for i in np.where(inv)[0]: geoms[i] = make_valid(geoms[i])
            gdf["geometry"] = geoms
        gdf = gdf[gdf["geometry"].notna() & ~gdf["geometry"].is_empty].copy()
    d = before - len(gdf)
    if d: log.warning(f"  {d} vides supprimees")
    return gdf

def _c2d(coords): return [(float(c[0]), float(c[1])) for c in coords]
def _polys(g):
    if g is None or g.is_empty: return []
    if g.geom_type == "Polygon": return [g]
    if g.geom_type == "MultiPolygon": return list(g.geoms)
    if g.geom_type == "GeometryCollection": return [x for x in g.geoms if x.geom_type == "Polygon"]
    return []
def _lines(g):
    if g is None or g.is_empty: return []
    if g.geom_type == "LineString": return [g]
    if g.geom_type == "MultiLineString": return list(g.geoms)
    return []

def geom_to_features(geom, tags, action="create"):
    r = []
    if geom.geom_type == "Point":
        r.append({"action": action, "gt": "Point",
                  "cc": [(round(geom.x,7), round(geom.y,7))], "tags": tags})
    elif geom.geom_type in ("LineString", "MultiLineString"):
        for ls in _lines(geom):
            c = _c2d(ls.coords)
            if len(c) >= 2:
                r.append({"action": action, "gt": "LineString",
                          "cc": [(round(x,7),round(y,7)) for x,y in c], "tags": tags})
    elif geom.geom_type in ("Polygon", "MultiPolygon"):
        for p in _polys(geom):
            c = _c2d(p.exterior.coords)
            if len(c) >= 4:
                r.append({"action": action, "gt": "Polygon",
                          "cc": [(round(x,7),round(y,7)) for x,y in c], "tags": tags})
    return r

# ══════════════════════════════════════════════════
#  MULTI-MILLÉSIMES
# ══════════════════════════════════════════════════
def find_all_millesimes(search_root):
    results = []
    for bd_dir in sorted(search_root.glob("BDTOPO_*D971*")):
        gpkg_files = sorted(bd_dir.rglob("*.gpkg"))
        if gpkg_files:
            m = re.search(r"(\d{4}-\d{2}-\d{2})", bd_dir.name)
            date_str = m.group(1) if m else bd_dir.name
            results.append((date_str, gpkg_files[0]))
    results.sort(key=lambda x: x[0])
    return results

def find_bdtopo_data(theme, search_root=None, millesime=None):
    roots = [r for r in [search_root, PROJECT_ROOT] if r and r.exists()]
    all_m = []
    for root in roots: all_m.extend(find_all_millesimes(root))
    if not all_m: raise FileNotFoundError(f"Aucun .gpkg BD TOPO pour {theme}.")
    if millesime:
        matches = [p for d, p in all_m if millesime in d]
        if matches: return matches[0]
        raise FileNotFoundError(f"Millesime {millesime} non trouve. Dispo: {[d for d,_ in all_m]}")
    return all_m[-1][1]

# ══════════════════════════════════════════════════
#  UTILITAIRES CHAMPS
# ══════════════════════════════════════════════════
def _get(row, *keys):
    for k in keys:
        v = row.get(k)
        if v is not None:
            s = str(v).strip()
            if s not in ("", "None", "nan", "NaN", "<NA>", "NaT"): return s
    return None

def _getf(row, *keys):
    v = _get(row, *keys)
    if v is None: return None
    try:
        f = float(v); return f if f > 0 else None
    except: return None

def _geti(row, *keys):
    v = _get(row, *keys)
    if v is None: return None
    try:
        i = int(float(v)); return i if i > 0 else None
    except: return None

# ══════════════════════════════════════════════════
#  CONVERTISSEURS (retours bibi + benoitdd intégrés)
# ══════════════════════════════════════════════════
def ign_bati_to_osm(row):
    nature = _get(row, "NATURE", "nature") or ""
    tags = dict(NATURE_BATI_MAP.get(nature, {"building": "yes"}))

    usage1 = _get(row, "USAGE1", "usage_1", "USAGE_1") or ""

    # Religieux : place_of_worship + fixme (retour benoitdd + bibi)
    if usage1 == "Religieux":
        tags["building"] = "yes"
        tags["amenity"] = "place_of_worship"
        tags["fixme"] = "Verifier religion et denomination"
    elif usage1:
        bt = USAGE1_BATI_MAP.get(usage1)
        if bt and tags.get("building") == "yes":
            tags["building"] = bt

    # Commercial : fixme retail vs bureaux (retour bibi)
    if usage1 == "Commercial et services":
        tags["fixme"] = "Verifier si retail (boutiques) ou commercial (bureaux)"

    usage2 = _get(row, "USAGE2", "usage_2", "USAGE_2") or ""
    if usage2 and usage2 != usage1:
        if usage2 == "Religieux":
            tags["building:use"] = "religious"
        else:
            bt2 = USAGE1_BATI_MAP.get(usage2)
            if bt2 and bt2 != "yes": tags["building:use"] = bt2

    if h := _getf(row, "HAUTEUR", "hauteur"):
        tags["height"] = str(round(h, 1))
    # NB_ETAGES : IGN inclut le RDC, convention identique a OSM (retour bibi verifie)
    if n := _geti(row, "NB_ETAGES", "nombre_d_etages", "nb_etages"):
        tags["building:levels"] = str(n)
    if nl := _geti(row, "NB_LOGEMENTS", "nombre_de_logements", "nb_logements"):
        tags["building:flats"] = str(nl)

    leger = _get(row, "LEGER", "construction_legere", "leger")
    if leger and leger.lower() in ("oui", "true", "1"):
        if tags.get("building") == "yes": tags["building"] = "shed"

    etat = _get(row, "ETAT", "etat_de_l_objet", "etat") or ""
    if "ruine" in etat.lower(): tags["ruins"] = "yes"
    elif "construction" in etat.lower(): tags["building"] = "construction"

    tags["source"] = "IGN BD TOPO"
    return tags

def ign_road_to_osm(row):
    nature = _get(row, "NATURE", "nature") or ""
    tags = dict(NATURE_ROUTE_MAP.get(nature, {"highway": "road"}))

    name = _get(row, "NOM_1_G", "nom_1_gauche", "NOM_1_D", "nom_1_droite",
                "NOM_VOIE_GAUCHE", "NOM_VOIE_DROITE")
    if name: tags["name"] = name

    ref = _get(row, "NUMERO", "numero", "CODE_ROUTE")
    if ref:
        tags["ref"] = ref
        if ref.startswith("D") and tags.get("highway") in ("primary", "secondary", "road"):
            tags["highway"] = "secondary"
        elif ref.startswith("N"):
            tags["highway"] = "primary"

    # IMPORTANCE pour affiner primary -> trunk (retour bibi)
    importance = _get(row, "IMPORTANCE", "importance")
    if importance and importance in ("1", "2") and tags.get("highway") == "primary":
        tags["highway"] = "trunk"

    sens = _get(row, "SENS", "sens_de_circulation")
    if sens == "Sens direct": tags["oneway"] = "yes"
    elif sens == "Sens inverse": tags["oneway"] = "-1"
    elif sens == "Double sens": tags["oneway"] = "no"

    # VITESSE_MOYENNE_VL : PAS importe comme maxspeed (retour bibi)
    # C'est la vitesse moyenne observee, pas la limite reglementaire

    if w := _getf(row, "LARGEUR_DE_CHAUSSEE", "largeur_de_chaussee"):
        tags["width"] = str(round(w, 1))
    if lanes := _geti(row, "NB_VOIES", "nombre_de_voies", "nb_voies"):
        tags["lanes"] = str(lanes)

    ps = _geti(row, "POS_SOL", "position_par_rapport_au_sol", "pos_sol")
    if ps is not None:
        if ps < 0: tags.update({"tunnel": "yes", "layer": str(ps)})
        elif ps > 0: tags.update({"bridge": "yes", "layer": str(ps)})

    rev = _get(row, "REVETEMENT", "nature_de_la_restriction")
    if rev:
        surf_map = {"Bitume": "asphalt", "Béton": "concrete", "Terre": "ground",
                    "Pavé": "paving_stones", "Gravillons": "gravel", "Stabilisé": "compacted"}
        if s := surf_map.get(rev): tags["surface"] = s

    tags["source"] = "IGN BD TOPO"
    return tags

def ign_hydro_to_osm(row):
    nature = _get(row, "NATURE", "nature") or ""
    tags = dict(NATURE_HYDRO_MAP.get(nature, {"waterway": "stream"}))
    name = _get(row, "NOM_C_EAU", "toponyme", "NOM", "nom")
    if name: tags["name"] = name
    regime = _get(row, "REGIME", "regime")
    if regime: tags["intermittent"] = "yes" if "intermittent" in regime.lower() else "no"
    if w := _getf(row, "LARGEUR", "largeur"): tags["width"] = str(round(w, 1))
    tags["source"] = "IGN BD TOPO"
    return tags

def ign_plan_eau_to_osm(row):
    nature = _get(row, "NATURE", "nature") or ""
    tags = dict(NATURE_PLAN_EAU_MAP.get(nature, {"natural": "water"}))
    name = _get(row, "NOM", "toponyme", "nom")
    if name: tags["name"] = name
    tags["source"] = "IGN BD TOPO"
    return tags

def ign_sport_to_osm(row):
    nature = _get(row, "NATURE", "nature") or ""
    tags = dict(NATURE_SPORT_MAP.get(nature, {"leisure": "pitch"}))
    name = _get(row, "NOM", "toponyme", "nom")
    if name: tags["name"] = name
    tags["source"] = "IGN BD TOPO"
    return tags

def ign_cimetiere_to_osm(row):
    tags = {"landuse": "cemetery", "source": "IGN BD TOPO"}
    name = _get(row, "NOM", "toponyme", "nom")
    if name: tags["name"] = name
    nature = _get(row, "NATURE", "nature") or ""
    if "militaire" in nature.lower(): tags["cemetery"] = "war_cemetery"
    return tags

def ign_reservoir_to_osm(row):
    tags = {"man_made": "reservoir", "source": "IGN BD TOPO"}
    name = _get(row, "NOM", "toponyme", "nom")
    if name: tags["name"] = name
    nature = _get(row, "NATURE", "nature") or ""
    if "eau" in nature.lower(): tags["content"] = "water"
    if h := _getf(row, "HAUTEUR", "hauteur"): tags["height"] = str(round(h, 1))
    return tags

def ign_vegetation_to_osm(row):
    nature = _get(row, "NATURE", "nature") or ""
    tags = (NATURE_VEGETATION_MAP.get(nature) or
            NATURE_VEGETATION_MAP.get(nature.lower()) or
            {"natural": "wood"})
    tags = dict(tags)
    name = _get(row, "NOM", "toponyme", "nom")
    if name: tags["name"] = name
    tfv = _get(row, "TFV", "tfv")
    if tfv:
        tfv_map = {
            "Forêt fermée de feuillus": {"leaf_type": "broadleaved"},
            "Forêt fermée de conifères": {"leaf_type": "needleleaved"},
            "Mangrove": {"natural": "wetland", "wetland": "mangrove"},
            "Bananeraie": {"landuse": "orchard", "trees": "banana_plants"},
            "Canne à sucre": {"landuse": "farmland", "crop": "sugarcane"},
        }
        extra = tfv_map.get(tfv) or tfv_map.get(tfv.lower() if tfv else "")
        if extra: tags.update(extra)
    tags["source"] = "IGN BD TOPO"
    return tags

def ign_pylone_to_osm(row):
    tags = {"power": "tower", "source": "IGN BD TOPO"}
    if h := _getf(row, "HAUTEUR", "hauteur"): tags["height"] = str(round(h, 1))
    return tags

def ign_ligne_elec_to_osm(row):
    tags = {"power": "line", "source": "IGN BD TOPO"}
    v = _get(row, "TENSION", "tension")
    if v: tags["voltage"] = v
    return tags

def ign_aerodrome_to_osm(row):
    nature = _get(row, "NATURE", "nature") or ""
    tags = {"aeroway": "heliport"} if "héliport" in nature.lower() else {"aeroway": "aerodrome"}
    name = _get(row, "NOM", "toponyme", "nom")
    if name: tags["name"] = name
    if icao := _get(row, "CODE_OACI", "code_oaci"): tags["icao"] = icao
    if iata := _get(row, "CODE_IATA", "code_iata"): tags["iata"] = iata
    tags["source"] = "IGN BD TOPO"
    return tags

def ign_equipement_to_osm(row):
    nature = _get(row, "NATURE", "nature") or ""
    tags = dict(NATURE_EQUIP_MAP.get(nature, {}))
    if not tags:
        nl = nature.lower()
        if "parking" in nl: tags = {"amenity": "parking"}
        elif "port" in nl and "aero" not in nl: tags = {"leisure": "marina"}
        elif "gare" in nl and "routiere" in nl: tags = {"amenity": "bus_station"}
        elif "gare" in nl and "maritime" in nl: tags = {"amenity": "ferry_terminal"}
        elif "gare" in nl: tags = {"railway": "station"}
        elif "arret" in nl or "arrêt" in nl: tags = {"highway": "bus_stop"}
        elif "peage" in nl or "péage" in nl: tags = {"barrier": "toll_booth"}
        elif "carrefour" in nl: tags = {"highway": "junction"}
        elif "rond" in nl: tags = {"junction": "roundabout"}
        elif "aire" in nl: tags = {"highway": "rest_area"}
        elif "heliport" in nl or "héliport" in nl: tags = {"aeroway": "heliport"}
        elif "aerogare" in nl or "aérogare" in nl: tags = {"aeroway": "terminal"}
        else: tags = {"man_made": "yes", "fixme": f"equipement_transport:{nature}"}
    name = _get(row, "NOM", "toponyme", "nom")
    if name: tags["name"] = name
    tags["source"] = "IGN BD TOPO"
    return tags

def ign_construction_to_osm(row):
    nature = _get(row, "NATURE", "nature") or ""
    tags = dict(NATURE_CONSTRUCTION_MAP.get(nature, {}))
    if not tags:
        nl = nature.lower()
        if "barrage" in nl: tags = {"waterway": "dam"}
        elif "piscine" in nl: tags = {"leisure": "swimming_pool"}
        elif "pont" in nl: tags = {"man_made": "bridge"}
        elif "stade" in nl: tags = {"building": "stadium"}
        elif "tribune" in nl: tags = {"building": "grandstand"}
        elif "mur" in nl: tags = {"barrier": "wall"}
        elif "escalier" in nl: tags = {"highway": "steps"}
        else: tags = {"building": "yes"}
    name = _get(row, "NOM", "toponyme", "nom")
    if name: tags["name"] = name
    tags["source"] = "IGN BD TOPO"
    return tags

def ign_admin_to_osm(row):
    tags = {"boundary": "administrative", "admin_level": "8", "source": "IGN BD TOPO"}
    name = _get(row, "NOM", "nom_officiel", "NOM_OFFICIEL", "nom")
    if name: tags["name"] = name
    code = _get(row, "CODE_INSEE", "code_insee", "INSEE_COM", "insee_com")
    if code: tags["ref:INSEE"] = code
    if pop := _geti(row, "POPULATION", "population"): tags["population"] = str(pop)
    return tags

# ══════════════════════════════════════════════════
#  AUTH
# ══════════════════════════════════════════════════
def get_osm_api(dry_run=True):
    url = "https://api06.dev.openstreetmap.org" if dry_run else "https://api.openstreetmap.org"
    if dry_run: log.warning("MODE DRY RUN")
    cid, csec, tok = (os.environ.get(k,"") for k in ("OSM_CLIENT_ID","OSM_CLIENT_SECRET","OSM_ACCESS_TOKEN"))
    if not all([cid,csec,tok]):
        log.error("Credentials manquantes. python scripts/osm_auth.py"); sys.exit(1)
    session = OAuth2Session(client_id=cid, token={"access_token": tok, "token_type": "Bearer"})
    return osmapi.OsmApi(api=url, session=session, appid="GwadaBot/2.1")

# ══════════════════════════════════════════════════
#  CHARGEMENT
# ══════════════════════════════════════════════════
def load_bdtopo_layer(gpkg_path, layer_name):
    log.info(f"Chargement : {layer_name}")
    available = fiona.listlayers(str(gpkg_path))
    if layer_name not in available:
        matches = [l for l in available if layer_name.lower() in l.lower()]
        if matches: layer_name = matches[0]; log.warning(f"  -> {layer_name}")
        else: raise ValueError(f"'{layer_name}' absent. Dispo: {available}")
    t0 = time.time()
    gdf = gpd.read_file(gpkg_path, layer=layer_name)
    log.info(f"  Lecture : {time.time()-t0:.1f}s ({len(gdf):,} lignes)")
    log.debug(f"  Colonnes: {list(gdf.columns)}")
    if gdf.crs and gdf.crs.to_epsg() != 4326:
        t0 = time.time(); gdf = gdf.to_crs(epsg=4326); log.info(f"  Reprojection : {time.time()-t0:.1f}s")
    t0 = time.time(); gdf = strip_z_vectorized(gdf); log.info(f"  Strip Z : {time.time()-t0:.1f}s")
    t0 = time.time(); gdf = validate_geometries(gdf); log.info(f"  Validation : {time.time()-t0:.1f}s")
    log.info(f"  {len(gdf):,} objets prets")
    return gdf

# ══════════════════════════════════════════════════
#  STATS
# ══════════════════════════════════════════════════
def compute_stats_fast(gdf, converter_fn):
    type_names = np.array([g.geom_type if g is not None else "None" for g in gdf["geometry"].values])
    unique, counts = np.unique(type_names, return_counts=True)
    type_counts = {str(t): int(c) for t, c in zip(unique, counts)}
    sample_size = min(2000, len(gdf))
    idx = np.random.RandomState(42).choice(len(gdf), sample_size, replace=False)
    sc = 0
    for i in idx:
        g = gdf["geometry"].values[i]
        if g is None: continue
        try:
            if g.geom_type in ("Polygon","MultiPolygon"):
                for p in _polys(g): sc += len(list(p.exterior.coords))
            elif g.geom_type in ("LineString","MultiLineString"):
                for ls in _lines(g): sc += len(list(ls.coords))
            else: sc += 1
        except: pass
    total_coords = int(sc * len(gdf) / sample_size)
    tag_idx = np.random.RandomState(42).choice(len(gdf), min(1000, len(gdf)), replace=False)
    tv = {}
    for i in tag_idx:
        for k, v in converter_fn(gdf.iloc[int(i)]).items():
            tv.setdefault(k, Counter())[str(v)] += 1
    factor = len(gdf) / len(tag_idx)
    top = {k: [(v, int(c*factor)) for v, c in ctr.most_common(5)] for k, ctr in tv.items()}
    n_ways = sum(type_counts.get(t, 0) for t in ("Polygon","MultiPolygon","LineString","MultiLineString"))
    return {"total": len(gdf), "geom_types": type_counts, "total_coords": total_coords,
            "estimated_nodes": total_coords, "estimated_ways": n_ways, "tag_distribution": top}

# ══════════════════════════════════════════════════
#  COMPARAISON MILLÉSIMES
# ══════════════════════════════════════════════════
def compare_millesimes(search_root, layer_name):
    all_m = find_all_millesimes(search_root)
    if len(all_m) < 2: log.info("Pas assez de millesimes."); return
    log.info(f"\n{'='*60}")
    log.info(f"COMPARAISON — {layer_name}")
    log.info(f"{'='*60}")
    counts = []
    for date_str, gpkg_path in all_m:
        try:
            available = fiona.listlayers(str(gpkg_path))
            matches = [l for l in available if layer_name.lower() in l.lower()]
            if not matches: counts.append((date_str, 0)); continue
            gdf = gpd.read_file(gpkg_path, layer=matches[0], ignore_geometry=True)
            counts.append((date_str, len(gdf)))
        except: counts.append((date_str, -1))
    for i, (d, c) in enumerate(counts):
        delta = ""
        if i > 0 and counts[i-1][1] > 0 and c > 0:
            diff = c - counts[i-1][1]
            delta = f"  ({'+' if diff >= 0 else ''}{diff:,})"
        log.info(f"  {d} : {c:>10,} objets{delta}")
    if counts:
        first_c = next((c for _, c in counts if c > 0), 0)
        last_c = counts[-1][1]
        if first_c > 0 and last_c > 0:
            total_diff = last_c - first_c
            log.info(f"\n  Total : {'+' if total_diff >= 0 else ''}{total_diff:,} ({counts[0][0]} -> {counts[-1][0]})")

# ══════════════════════════════════════════════════
#  .OSC
# ══════════════════════════════════════════════════
def _esc(v): return saxutils.escape(str(v))

def generate_osc(features, output_path, cs_id=1):
    parts = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<osmChange version="0.6" generator="GwadaBot/2.1">']
    nid, wid = -1, -1
    groups = {}
    for f in features: groups.setdefault(f.get("action","create"), []).append(f)
    for act in ("create","modify","delete"):
        items = groups.get(act, [])
        if not items: continue
        parts.append(f"  <{act}>")
        for feat in items:
            gt, cc, tags = feat.get("gt","Point"), feat.get("cc",[]), feat.get("tags",{})
            txml = "".join(f'<tag k="{_esc(k)}" v="{_esc(v)}"/>' for k,v in tags.items())
            if gt == "Point" and cc:
                lon,lat = cc[0]
                parts.append(f'<node id="{nid}" changeset="{cs_id}" version="1" '
                             f'lat="{lat:.7f}" lon="{lon:.7f}">{txml}</node>')
                nid -= 1
            elif gt in ("LineString","Polygon"):
                nd_ids = []
                for lon,lat in cc:
                    parts.append(f'<node id="{nid}" changeset="{cs_id}" version="1" '
                                 f'lat="{lat:.7f}" lon="{lon:.7f}"/>')
                    nd_ids.append(nid); nid -= 1
                if gt == "Polygon" and nd_ids and nd_ids[0] != nd_ids[-1]:
                    nd_ids.append(nd_ids[0])
                nxml = "".join(f'<nd ref="{nd}"/>' for nd in nd_ids)
                parts.append(f'<way id="{wid}" changeset="{cs_id}" version="1">{nxml}{txml}</way>')
                wid -= 1
        parts.append(f"  </{act}>")
    parts.append("</osmChange>")
    output_path.write_text("\n".join(parts), encoding="utf-8")
    return abs(nid)-1, abs(wid)-1

# ══════════════════════════════════════════════════
#  PIPELINE
# ══════════════════════════════════════════════════
def run_import(theme, layer_name, converter_fn, dry_run=True, local_data=None,
               use_conflation=False, sample_batches=DRY_RUN_SAMPLE_BATCHES, millesime=None):
    t_start = time.time()
    log.info("=" * 60)
    log.info(f"GwadaBot — {theme} / {layer_name}")
    log.info("=" * 60)

    search_root = Path(local_data) if local_data else PROJECT_ROOT
    all_m = find_all_millesimes(search_root)
    if all_m: log.info(f"Millesimes : {[d for d,_ in all_m]}")

    gpkg_path = find_bdtopo_data(theme, search_root, millesime)
    m_match = re.search(r"(\d{4}-\d{2}-\d{2})", str(gpkg_path))
    m_date = m_match.group(1) if m_match else "?"
    log.info(f"Utilise : {m_date} | {gpkg_path.name}")

    cs_tags = dict(CHANGESET_TAGS)
    cs_tags["source"] = f"IGN BD TOPO {m_date} -- Licence Ouverte Etalab 2.0"

    gdf = load_bdtopo_layer(gpkg_path, layer_name)
    total = len(gdf)

    if len(all_m) >= 2: compare_millesimes(search_root, layer_name)

    t0 = time.time()
    stats = compute_stats_fast(gdf, converter_fn)
    log.info(f"Stats : {time.time()-t0:.1f}s | {stats['total']:,} obj | ~{stats['estimated_nodes']:,}n ~{stats['estimated_ways']:,}w")
    for k, vals in stats["tag_distribution"].items():
        if k == "source": continue
        log.info(f"  {k}: {', '.join(f'{v}({c:,})' for v,c in vals[:4])}")

    sp = LOG_DIR / f"stats_{theme.lower()}_{m_date}.json"
    sj = {**{k:v for k,v in stats.items() if k != "tag_distribution"}, "millesime": m_date,
          "tag_distribution": {k: [(str(v),c) for v,c in t] for k,t in stats["tag_distribution"].items()}}
    sp.write_text(json.dumps(sj, indent=2, ensure_ascii=False), encoding="utf-8")

    engine = None
    if use_conflation:
        log.info("Conflation parallele...")
        t0 = time.time()
        try:
            from conflation import ConflationEngine, load_osm_parallel
            tf = THEME_TAG_FILTER.get(theme, "")
            osm_el = load_osm_parallel(BBOX_GUADELOUPE, tag_filter=tf, grid=4, workers=4)
            engine = ConflationEngine.from_overpass(osm_el)
            log.info(f"  Pret : {time.time()-t0:.1f}s ({engine.count:,} el.)")
        except Exception as exc: log.warning(f"  Impossible : {exc}")

    api = get_osm_api(dry_run=dry_run)
    total_batches = (total + BATCH_SIZE - 1) // BATCH_SIZE
    max_batches = min(sample_batches, total_batches) if dry_run else total_batches
    log.info(f"{'DRY RUN' if dry_run else 'PRODUCTION'} : {max_batches}/{total_batches} batches")

    theme_dir = LOG_DIR / f"{theme.lower()}_{m_date}"
    theme_dir.mkdir(exist_ok=True)

    processed = total_features = total_skipped = total_nodes = total_ways = batch_num = 0

    for start in range(0, total, BATCH_SIZE):
        if batch_num >= max_batches: break
        end = min(start + BATCH_SIZE, total)
        batch = gdf.iloc[start:end]; batch_num += 1
        features, skipped = [], 0
        for idx in range(len(batch)):
            row = batch.iloc[idx]; geom = row.geometry
            if geom is None or geom.is_empty: skipped += 1; continue
            tags = converter_fn(row); action = "create"
            if engine:
                r = engine.find_match(geom, tags)
                if r.action == "skip": skipped += 1; continue
                action = r.action
                if r.merged_tags: tags = r.merged_tags
            features.extend(geom_to_features(geom, tags, action=action))
        total_skipped += skipped
        if not features: continue
        total_features += len(features)
        osc_path = theme_dir / f"batch_{batch_num:04d}.osc"
        if dry_run:
            n, w = generate_osc(features, osc_path, cs_id=999)
            total_nodes += n; total_ways += w
            log.info(f"  Batch {batch_num}/{max_batches}: {len(features)} feat -> {osc_path.name} ({n}n {w}w)")
        else:
            try:
                cs = api.ChangesetCreate(cs_tags)
                n, w = generate_osc(features, osc_path, cs_id=cs)
                total_nodes += n; total_ways += w; api.ChangesetClose(cs)
                log.info(f"  CS#{cs}: {n}n {w}w")
            except Exception as exc: log.error(f"  Erreur: {exc}")
        processed += len(batch)
        if not dry_run:
            time.sleep(DELAY_BETWEEN_BATCHES)
            if processed >= MAX_PER_DAY: log.warning("Limite jour."); break

    elapsed = time.time() - t_start
    log.info(f"\n{'='*60}")
    log.info(f"RESUME — {theme}/{layer_name} ({m_date})")
    log.info(f"{'='*60}")
    log.info(f"  Mode: {'DRY' if dry_run else 'PROD'} | Conflation: {'OUI('+str(engine.count)+')' if engine else 'NON'}")
    log.info(f"  Source: {total:,} | Traites: {processed:,} | Features: {total_features:,}")
    log.info(f"  Nodes: {total_nodes:,} | Ways: {total_ways:,} | Skip: {total_skipped:,}")
    log.info(f"  Duree: {elapsed:.1f}s | Batches: {batch_num} | Dir: {theme_dir.name}")
    if dry_run:
        log.info(f"\n  JOSM: {theme_dir / 'batch_0001.osc'}")
        log.info(f"  Prod: python scripts/gwadabot.py --theme {theme} --production")
    log.info(f"{'='*60}")

# ══════════════════════════════════════════════════
#  CLI — ADMINISTRATIF retire du --all (retour benoitdd)
# ══════════════════════════════════════════════════
THEME_CONFIG = {
    "BATI":          ("batiment",              ign_bati_to_osm),
    "TRANSPORT":     ("troncon_de_route",      ign_road_to_osm),
    "HYDROGRAPHIE":  ("troncon_hydrographique",ign_hydro_to_osm),
    "PLAN_EAU":      ("plan_d_eau",            ign_plan_eau_to_osm),
    "SPORT":         ("terrain_de_sport",      ign_sport_to_osm),
    "CIMETIERE":     ("cimetiere",             ign_cimetiere_to_osm),
    "RESERVOIR":     ("reservoir",             ign_reservoir_to_osm),
    "VEGETATION":    ("zone_de_vegetation",    ign_vegetation_to_osm),
    "PYLONE":        ("pylone",                ign_pylone_to_osm),
    "LIGNE_ELEC":    ("ligne_electrique",      ign_ligne_elec_to_osm),
    "AERODROME":     ("aerodrome",             ign_aerodrome_to_osm),
    "EQUIPEMENT":    ("equipement_de_transport",ign_equipement_to_osm),
    "CONSTRUCTION":  ("construction_surfacique",ign_construction_to_osm),
    "ADMINISTRATIF": ("commune",               ign_admin_to_osm),
}

# Themes importes en production (ADMINISTRATIF exclu — retour benoitdd)
IMPORT_THEMES = [t for t in THEME_CONFIG if t != "ADMINISTRATIF"]

def main():
    all_themes = list(THEME_CONFIG.keys())
    parser = argparse.ArgumentParser(
        description="GwadaBot v2.1 — Import OSM Guadeloupe (BD TOPO)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Themes : {', '.join(all_themes)}
(--all exclut ADMINISTRATIF, utiliser --theme ADMINISTRATIF explicitement)

Exemples :
  python scripts/gwadabot.py --theme BATI --dry-run
  python scripts/gwadabot.py --all --dry-run
  python scripts/gwadabot.py --theme BATI --millesime 2023-12-15 --dry-run
  python scripts/gwadabot.py --theme BATI --dry-run --conflation
  python scripts/gwadabot.py --list-layers
  python scripts/gwadabot.py --list-millesimes
  python scripts/gwadabot.py --compare batiment
  python scripts/gwadabot.py --theme TRANSPORT --production --conflation
""")
    parser.add_argument("--theme", choices=all_themes)
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--layer", type=str)
    parser.add_argument("--local-data", type=str)
    parser.add_argument("--dry-run", action="store_true", default=True)
    parser.add_argument("--production", action="store_true")
    parser.add_argument("--list-layers", action="store_true")
    parser.add_argument("--list-millesimes", action="store_true")
    parser.add_argument("--compare", type=str, metavar="COUCHE")
    parser.add_argument("--conflation", action="store_true")
    parser.add_argument("--sample", type=int, default=DRY_RUN_SAMPLE_BATCHES)
    parser.add_argument("--millesime", type=str)

    args = parser.parse_args()
    dry_run = not args.production
    search = Path(args.local_data) if args.local_data else PROJECT_ROOT

    if args.list_millesimes:
        all_m = find_all_millesimes(search)
        print(f"\n  Millesimes BD TOPO D971 ({len(all_m)}) :\n")
        for d, p in all_m: print(f"    {d}  ->  {p.name}")
        print(); sys.exit(0)

    if args.compare:
        compare_millesimes(search, args.compare); sys.exit(0)

    if args.list_layers:
        try:
            gpkg = find_bdtopo_data(args.theme or "BATI", search, args.millesime)
            layers = fiona.listlayers(str(gpkg))
            used = {v[0] for v in THEME_CONFIG.values()}
            print(f"\n  Couches dans {gpkg.name} ({len(layers)}) :\n")
            for l in layers:
                marker = " <-- GwadaBot" if l in used else ""
                print(f"    {l}{marker}")
            print()
        except FileNotFoundError as e: log.error(str(e))
        sys.exit(0)

    if not args.theme and not args.all:
        parser.error("--theme ou --all requis")

    if args.production:
        log.warning("=" * 60)
        log.warning("  MODE PRODUCTION")
        log.warning("  Validation communautaire obtenue ?")
        log.warning("=" * 60)
        if input("\nTapez 'GUADELOUPE' : ").strip() != "GUADELOUPE":
            log.info("Annule."); sys.exit(0)

    themes = IMPORT_THEMES if args.all else [args.theme]
    for theme in themes:
        default_layer, converter = THEME_CONFIG[theme]
        run_import(
            theme=theme, layer_name=args.layer or default_layer, converter_fn=converter,
            dry_run=dry_run, local_data=args.local_data, use_conflation=args.conflation,
            sample_batches=args.sample, millesime=args.millesime,
        )
        if args.all and theme != themes[-1]: log.info("")

if __name__ == "__main__":
    main()
