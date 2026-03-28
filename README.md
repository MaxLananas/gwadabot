# GwadaBot

**Import automatisé OpenStreetMap pour la Guadeloupe (971) — BD TOPO IGN**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://python.org)
[![Licence Ouverte 2.0](https://img.shields.io/badge/source-Licence%20Ouverte%202.0-green.svg)](https://www.etalab.gouv.fr/licence-ouverte-open-licence)
[![ODbL Compatible](https://img.shields.io/badge/ODbL-compatible-brightgreen.svg)](https://opendatacommons.org/licenses/odbl/)
[![OSM Import](https://img.shields.io/badge/wiki-Import%2FGwadaBot-orange.svg)](https://wiki.openstreetmap.org/wiki/Import/GwadaBot)

---

## Contexte

La couverture OpenStreetMap de la Guadeloupe (16.2°N, -61.5°W, 1 628 km², ~400 000 hab.) présente des lacunes structurelles. Une analyse Overpass (mars 2026) révèle :

| Métrique | OSM actuel | BD TOPO IGN | Couverture |
|---|---|---|---|
| Bâtiments | < 50 000 | 379 503 | ~13% |
| Routes | 57 742 ways | 72 695 tronçons | ~79% |
| Cours d'eau | partiel | 16 796 tronçons | < 30% estimé |
| Végétation | quasi-absent | 66 970 zones | < 5% |
| Terrains de sport | ~50 | 747 | ~7% |

GwadaBot exploite la BD TOPO IGN v3.5 (Licence Ouverte Etalab 2.0, compatible ODbL) pour combler ces lacunes via un pipeline vectorisé avec conflation spatiale R-tree.

## Données source

**IGN BD TOPO v3.5** — GeoPackage, projection native RGAF09 UTM20N (EPSG:5490), reprojeté en WGS84 (EPSG:4326) à l'exécution.

### Millésimes disponibles

```
2021-03-15    BDT_3-0    382 692 bâtiments    69 670 routes
2023-12-15    BDT_3-3    380 637 bâtiments    71 552 routes    (-2 055 / +1 882)
2024-03-15    BDT_3-3    380 605 bâtiments    71 643 routes    (-32 / +91)
2025-03-15    BDT_3-4    380 064 bâtiments    72 442 routes    (-541 / +799)
2025-06-15    BDT_3-5    379 737 bâtiments    72 736 routes    (-327 / +294)
2025-09-15    BDT_3-5    379 674 bâtiments    72 743 routes    (-63 / +7)
2025-12-15    BDT_3-5    379 503 bâtiments    72 695 routes    (-171 / -48)
```

Delta total 2021→2025 : bâtiments -3 189 (nettoyage IGN : fusion doublons, bâtiments démolis post-cyclones), routes +3 025 (nouvelles voies).

### Périmètre d'import — 14 couches, ~538 000 objets

| Couche | Objets | Géométrie | Nodes estimés | Tags principaux |
|---|---|---|---|---|
| `batiment` | 379 503 | MultiPolygon | ~2 834 000 | `building`, `height`, `building:levels`, `building:flats` |
| `troncon_de_route` | 72 695 | LineString | ~738 000 | `highway`, `maxspeed`, `oneway`, `lanes`, `width`, `surface` |
| `zone_de_vegetation` | 66 970 | MultiPolygon | ~5 084 000 | `natural=wood`, `landuse`, `leaf_type`, `wetland=mangrove`, `crop=sugarcane` |
| `troncon_hydrographique` | 16 796 | LineString | ~295 000 | `waterway`, `name`, `intermittent`, `width` |
| `terrain_de_sport` | 747 | MultiPolygon | ~4 900 | `leisure=pitch`, `sport` |
| `pylone` | 662 | Point | 662 | `power=tower`, `height` |
| `reservoir` | 418 | MultiPolygon | ~8 700 | `man_made=reservoir`, `content`, `height` |
| `equipement_de_transport` | 384 | MultiPolygon | ~3 500 | `amenity=parking`, `aeroway=terminal`, `amenity=bus_station` |
| `plan_d_eau` | 71 | MultiPolygon | ~4 500 | `natural=water`, `water=pond\|reservoir\|lake` |
| `construction_surfacique` | 56 | MultiPolygon | ~630 | `waterway=dam`, `leisure=swimming_pool`, `man_made=bridge` |
| `cimetiere` | 50 | MultiPolygon | ~1 200 | `landuse=cemetery` |
| `commune` | 32 | MultiPolygon | ~139 000 | `boundary=administrative`, `admin_level=8`, `ref:INSEE` |
| `ligne_electrique` | 28 | LineString | ~680 | `power=line`, `voltage` |
| `aerodrome` | 9 | MultiPolygon | ~520 | `aeroway=aerodrome\|heliport`, `icao`, `iata` |
| **Total** | **~538 421** | | **~9 115 000** | |

### Distribution des tags (couche `batiment`, échantillon n=1000, extrapolé)

```
building         : yes (227k), residential (134k), commercial (15k), farm (2k), industrial (1k)
height           : 4.2m (13k), 3.6m (12k), 3.5m (12k), 7.0m (8k), 3.0m (6k)
building:levels  : 1 (118k), 2 (20k), 3 (3.4k)
building:flats   : 1 (118k), 2 (6.5k), 3 (3.8k)
building:use     : commercial (3.4k), residential (1.5k)
ruins            : yes (759)
```

### Distribution des tags (couche `troncon_de_route`, échantillon n=1000, extrapolé)

```
highway          : secondary (40k), track (15k), unclassified (11k), path (4k), steps (1.3k)
oneway           : no (62k), yes (4.5k), -1 (1.9k)
maxspeed         : 1 (15k), 10 (11k), 40 (7.6k), 50 (6.8k)
width            : 5.0 (24k), 3.0 (8.4k), 4.0 (5.8k)
lanes            : 2 (32k), 1 (10k)
surface          : unpaved (11k)
bridge           : yes (1.3k)
junction         : roundabout (945)
```

## Architecture technique

```
scripts/
  gwadabot.py          Pipeline principal
  conflation.py        Moteur de conflation spatiale
  analyze.py           Analyse Overpass multi-zones
  osm_auth.py          OAuth 2.0 OOB flow
```

### Pipeline de traitement (`gwadabot.py`)

```
GeoPackage (.gpkg)
  │
  ├─ gpd.read_file()              Lecture via pyogrio (backend GDAL)
  │
  ├─ .to_crs(epsg=4326)           Reprojection RGAF09 UTM20N → WGS84
  │
  ├─ shapely.force_2d()           Strip Z-coords vectorisé
  │  (fallback: shapely.ops.transform si Shapely < 2.0)
  │
  ├─ shapely.make_valid()         Validation géométrique vectorisée
  │
  ├─ compute_stats_fast()         Stats par échantillonnage (n=1000)
  │  (numpy + Counter, pas d'iterrows)
  │
  ├─ ConflationEngine             [optionnel] Matching spatial R-tree
  │  ├─ load_osm_parallel()       Overpass 4×4 sous-zones, 4 threads
  │  └─ STRtree.nearest()         Recherche plus proche voisin O(log n)
  │
  ├─ geom_to_features()           Décomposition Multi* → features unitaires
  │
  └─ generate_osc()               Sérialisation XML .osc (nodes + ways)
       → logs/<theme>_<millesime>/batch_NNNN.osc
```

### Performances mesurées (379k bâtiments, i7-10th gen, 16 Go RAM)

| Étape | Durée | Méthode |
|---|---|---|
| Lecture GeoPackage | 6.7s | `pyogrio` (GDAL natif) |
| Reprojection EPSG:5490 → 4326 | 1.4s | `geopandas.to_crs` (proj4) |
| Strip Z-coords (379k geoms) | 0.7s | `shapely.force_2d` vectorisé |
| Validation géométrique | 1.2s | `shapely.make_valid` vectorisé |
| Calcul statistiques | 1.3s | Échantillonnage numpy, n=2000 |
| Génération 3 batches .osc | 0.3s | String concatenation + write |
| **Total dry-run (3 batches)** | **12s** | |

Comparaison avec approche naïve (iterrows + transform Python pur) : ~105s → gain **8.7x**.

### Moteur de conflation (`conflation.py`)

```
Overpass API (overpass-api.de)
  │
  ├─ _subdivide_bbox()       BBOX Guadeloupe → 16 sous-zones (4×4)
  │
  ├─ ThreadPoolExecutor(4)   4 requêtes parallèles
  │  └─ _fetch_zone()        [out:json][timeout:45], retry ×3, backoff 5s
  │
  ├─ Déduplication           set() sur element.id
  │
  └─ ConflationEngine
     ├─ STRtree(points)      Index spatial R-tree sur centroïdes OSM
     ├─ .nearest(geom)       Plus proche voisin en O(log n)
     └─ haversine()          Distance métrique (rayon terrestre 6 371 km)
```

Seuils de décision :

| Distance (Haversine) | Action | Logique |
|---|---|---|
| d < 10 m | `skip` ou `update` (tags) | Même objet, position cohérente |
| 10 m ≤ d < 50 m | `update` (geom + tags) | Objet déplacé ou imprécision |
| d ≥ 50 m | `create` | Objet absent d'OSM |

Stratégie de fusion des tags :

```
IGN prioritaire : highway, waterway, building, surface, maxspeed, height,
                  building:levels, bridge, tunnel, layer, width, lanes,
                  man_made, oneway, ref, power, leisure, landuse, natural,
                  aeroway

OSM prioritaire : name, name:fr, name:gcf, alt_name, wikipedia, wikidata,
                  website, phone, opening_hours, wheelchair, description
```

### Résolution des noms de colonnes

La BD TOPO v3.x utilise des noms de colonnes variables selon les versions (MAJUSCULES en v3.0, snake_case en v3.5). Le bot utilise un résolveur multi-clés :

```python
def _get(row, *keys):
    """Cherche la première clé non-vide parmi les variantes."""
    # Ex: _get(row, "NATURE", "nature", "NATURE_OBJET")
```

Cela garantit la compatibilité avec les 7 millésimes (v3.0 à v3.5).

### Mapping des attributs IGN → OSM

Le convertisseur `ign_bati_to_osm()` exploite 6 champs :

```
NATURE       → building type (greenhouse, chapel, tower, bunker...)
USAGE1       → building type affiné (residential, commercial, industrial, farm...)
USAGE2       → building:use (usage secondaire)
HAUTEUR      → height (float, arrondi 0.1m)
NB_ETAGES    → building:levels (int)
NB_LOGEMENTS → building:flats (int)
LEGER        → building=shed si true
ETAT         → ruins=yes | building=construction
```

Le convertisseur `ign_vegetation_to_osm()` résout le champ `NATURE` avec fallback sur `TFV` (type de formation végétale, v3.5) :

```
Mangrove       → natural=wetland + wetland=mangrove
Bananeraie     → landuse=orchard + trees=banana_plants
Canne à sucre  → landuse=farmland + crop=sugarcane
Forêt fermée   → natural=wood + leaf_type=broadleaved|needleleaved|mixed
```

### Format de sortie (.osc)

Chaque batch génère un fichier OsmChange XML :

```xml
<?xml version="1.0" encoding="UTF-8"?>
<osmChange version="0.6" generator="GwadaBot/2.0">
  <create>
    <node id="-1" changeset="999" version="1" lat="16.2345678" lon="-61.5432100"/>
    <node id="-2" changeset="999" version="1" lat="16.2345700" lon="-61.5431900"/>
    <way id="-1" changeset="999" version="1">
      <nd ref="-1"/><nd ref="-2"/><nd ref="-1"/>
      <tag k="building" v="residential"/>
      <tag k="height" v="7.5"/>
      <tag k="building:levels" v="2"/>
      <tag k="source" v="IGN BD TOPO"/>
    </way>
  </create>
</osmChange>
```

Les polygones fermés sont sérialisés en ways avec le premier node répété en fin de séquence. Les MultiPolygon sont décomposés en ways individuels (les relations ne sont pas générées à ce stade).

## Installation

```bash
git clone https://github.com/MaxLananas/gwadabot
cd gwadabot
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
```

Dépendances : `geopandas`, `shapely>=2.0`, `fiona`, `pyogrio`, `osmapi`, `overpy`, `requests_oauthlib`, `python-dotenv`, `numpy`.

Données : BD TOPO Guadeloupe depuis [data.geopf.fr](https://data.geopf.fr/telechargement/) (dept. 971, format GeoPackage). Placer le dossier `BDTOPO_*_D971_*` à la racine du projet.

## Configuration

```bash
python scripts/osm_auth.py
```

Génère `.env` (non versionné) avec les credentials OAuth 2.0 pour l'API OSM.

## Commandes

```bash
# Analyse Overpass de l'état OSM (4 sous-zones, retry auto)
python scripts/analyze.py

# Lister les millésimes locaux
python scripts/gwadabot.py --list-millesimes

# Comparer une couche entre millésimes (lecture ignore_geometry=True)
python scripts/gwadabot.py --compare batiment
python scripts/gwadabot.py --compare troncon_de_route

# Lister les 54 couches du GeoPackage
python scripts/gwadabot.py --list-layers

# Dry-run : génération .osc sans envoi réseau
python scripts/gwadabot.py --theme BATI --dry-run
python scripts/gwadabot.py --all --dry-run
python scripts/gwadabot.py --theme BATI --dry-run --conflation
python scripts/gwadabot.py --theme BATI --dry-run --sample 10
python scripts/gwadabot.py --theme BATI --millesime 2021-03-15 --dry-run

# Production (requiert validation communautaire préalable)
python scripts/gwadabot.py --theme BATI --production --conflation
```

## Paramètres d'import

| Paramètre | Valeur | Justification |
|---|---|---|
| `BATCH_SIZE` | 500 objets/changeset | 5% de la limite OSM (10 000), facilite le revert partiel |
| `DELAY_BETWEEN_BATCHES` | 2 s | Courtoisie serveur |
| `MAX_PER_DAY` | 50 000 objets | Auto-limitation, ~100 changesets/jour |
| Conflation grid | 4×4 (16 zones) | Évite les timeouts Overpass sur la bbox complète |
| Conflation workers | 4 threads | Parallélisme réseau, pas CPU-bound |
| STRtree | Shapely 2.0+ | Recherche nearest-neighbor O(log n) vs O(n) brute-force |

## Validation communautaire

Conformément aux [Import Guidelines](https://wiki.openstreetmap.org/wiki/Import/Guidelines) :

- [x] Page wiki : [Import/GwadaBot](https://wiki.openstreetmap.org/wiki/Import/GwadaBot)
- [x] Proposition envoyée à [imports@openstreetmap.org](mailto:imports@openstreetmap.org)
- [x] Discussion sur [talk-fr@openstreetmap.org](mailto:talk-fr@openstreetmap.org)
- [x] Sujet ouvert sur [forum.openstreetmap.fr](https://forum.openstreetmap.fr/)
- [ ] Période de review communautaire en cours
- [ ] Intégration des retours
- [ ] Accord communautaire

Aucun envoi en production ne sera effectué sans accord explicite.

## Licence

| Composant | Licence |
|---|---|
| Code source | MIT |
| Données produites | ODbL (hérité d'OpenStreetMap) |
| Données source | [Licence Ouverte Etalab 2.0](https://www.etalab.gouv.fr/licence-ouverte-open-licence) (IGN BD TOPO) |
