"""
bygg_lager.py — bygger workshop-lagren för Malmö som GeoJSON-filer i mappen lager/.

Körs med geopandas-miljön:
    ~/Workspaces/geospatial/.venv/bin/python bygg_lager.py

Vad skriptet gör, steg för steg:
  1. Hämtar DeSO- och RegSO-områden för Malmö (kommunkod 1280) från SCB:s öppna WFS-tjänst.
  2. Hämtar folkmängd 2025 per DeSO (totalt, 0–19 år, 65+ år) från SCB:s statistikdatabas.
  3. Slår ihop DeSO-områdena till en kommungräns.
  4. Skapar tre dummylager (påhittade data) för att visa punkter, linjer och ytor.
  5. Förenklar geometrierna, gör om till WGS84 (lon/lat, krav i GeoJSON/geojson.io) och sätter färger.
  6. Skriver en fil per lager, en fil med alla lager och en lista (lager.json) som index.html läser.
"""

import json
import urllib.request
from pathlib import Path

import geopandas as gpd
from shapely.geometry import LineString, Point, Polygon

MAPP = Path(__file__).parent / "lager"
KOMMUN = "1280"  # Malmö
AR = "2025"      # statistikår för folkmängden
WFS = "https://geodata.scb.se/geoserver/stat/wfs"
PXWEB = "https://api.scb.se/OV0104/v1/doris/sv/ssd/BE/BE0101/BE0101Y/FolkmDesoAldKon"


# ---------- Hjälpfunktioner ----------

def hamta_wfs(lager):
    """Hämta ett SCB-lager för Malmö från WFS-tjänsten. Svaret är i SWEREF 99 TM (EPSG:3006)."""
    url = (f"{WFS}?service=WFS&version=2.0.0&request=GetFeature&typeNames=stat:{lager}"
           f"&outputFormat=application/json&CQL_FILTER=kommunkod='{KOMMUN}'")
    data = json.loads(urllib.request.urlopen(url, timeout=120).read())
    return gpd.GeoDataFrame.from_features(data["features"], crs="EPSG:3006")


def hamta_folkmangd(desokoder):
    """Hämta folkmängd per DeSO och åldersgrupp från SCB:s statistikdatabas (PxWeb)."""
    aldrar_unga = ["-4", "5-9", "10-14", "15-19"]
    aldrar_aldre = ["65-69", "70-74", "75-79", "80-"]
    fraga = {
        "query": [
            # SCB använder koden "<desokod>_DeSO2025" för 2025 års indelning.
            {"code": "Region", "selection": {"filter": "item", "values": [k + "_DeSO2025" for k in desokoder]}},
            {"code": "Alder", "selection": {"filter": "item", "values": ["totalt"] + aldrar_unga + aldrar_aldre}},
            {"code": "Kon", "selection": {"filter": "item", "values": ["1+2"]}},
            {"code": "Tid", "selection": {"filter": "item", "values": [AR]}},
        ],
        "response": {"format": "json"},
    }
    req = urllib.request.Request(PXWEB, data=json.dumps(fraga).encode(), headers={"Content-Type": "application/json"})
    svar = json.loads(urllib.request.urlopen(req, timeout=120).read().decode("utf-8-sig"))

    # Summera per DeSO: totalt, 0–19 år och 65+ år.
    res = {k: {"totalt": 0, "unga": 0, "aldre": 0} for k in desokoder}
    for rad in svar["data"]:
        region, alder = rad["key"][0].replace("_DeSO2025", ""), rad["key"][1]
        varde = int(rad["values"][0]) if rad["values"][0].isdigit() else 0
        if alder == "totalt":
            res[region]["totalt"] = varde
        elif alder in aldrar_unga:
            res[region]["unga"] += varde
        elif alder in aldrar_aldre:
            res[region]["aldre"] += varde
    return res


def avrunda(varde):
    """Avrunda koordinater till 5 decimaler (ca 1 m). Mindre filer, ingen synlig skillnad."""
    if isinstance(varde, (list, tuple)):
        return [avrunda(v) for v in varde]
    return round(varde, 5)


def skriv(gdf, filnamn):
    """Gör om till WGS84 och skriv en kompakt GeoJSON-fil. Returnerar listan med objekt."""
    gdf = gdf.to_crs("EPSG:4326")
    geo = json.loads(gdf.to_json(drop_id=True))
    for f in geo["features"]:
        f["geometry"]["coordinates"] = avrunda(f["geometry"]["coordinates"])
    (MAPP / filnamn).write_text(json.dumps(geo, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return geo["features"]


# ---------- 1–3. SCB-lager ----------

print("Hämtar DeSO och RegSO från SCB ...")
deso = hamta_wfs("DeSO_2025")
regso = hamta_wfs("RegSO_2025")
print(f"  {len(deso)} DeSO, {len(regso)} RegSO")

print("Hämtar folkmängd ...")
folk = hamta_folkmangd(list(deso["desokod"]))

# Räkna ut statistik per DeSO. Ytan räknas i SWEREF 99 TM (meter) innan omprojicering.
deso["folkmangd"] = deso["desokod"].map(lambda k: folk[k]["totalt"])
deso["andel_0_19"] = deso["desokod"].map(lambda k: round(100 * folk[k]["unga"] / max(folk[k]["totalt"], 1), 1))
deso["andel_65plus"] = deso["desokod"].map(lambda k: round(100 * folk[k]["aldre"] / max(folk[k]["totalt"], 1), 1))
deso["yta_km2"] = (deso.area / 1e6).round(2)
deso["inv_per_km2"] = (deso["folkmangd"] / deso["yta_km2"].clip(lower=0.01)).round(0).astype(int)

# Färg efter befolkningstäthet: fem lika stora grupper (kvintiler), ljusblått = glest, mörkblått = tätt.
farger = ["#eff3ff", "#bdd7e7", "#6baed6", "#3182bd", "#08519c"]
klass = deso["inv_per_km2"].rank(pct=True).mul(5).clip(upper=4.999).astype(int)
deso["fill"] = klass.map(lambda i: farger[i])
deso["fill-opacity"] = 0.6
deso["stroke"] = "#555555"
deso["stroke-width"] = 0.5
deso["title"] = deso["desokod"]

# RegSO: summera DeSO-statistiken per RegSO-område (varje DeSO hör till exakt ett RegSO).
per_regso = deso.groupby("regsokod")[["folkmangd"]].sum()
regso = regso.merge(per_regso, on="regsokod", how="left")
regso["inv_per_km2"] = (regso["folkmangd"] / (regso.area / 1e6)).round(0).astype(int)
regso["title"] = regso["regsonamn"]
regso["fill"] = "#ffffff"
regso["fill-opacity"] = 0.0
regso["stroke"] = "#d95f02"
regso["stroke-width"] = 2

# Kommungräns = alla DeSO i Malmö sammanslagna.
kommun = gpd.GeoDataFrame({"title": ["Malmö kommun"], "kommunkod": [KOMMUN],
                           "folkmangd": [int(deso["folkmangd"].sum())]},
                          geometry=[deso.union_all()], crs="EPSG:3006")
kommun["fill-opacity"] = 0.0
kommun["stroke"] = "#000000"
kommun["stroke-width"] = 3

# Förenkla gränserna (10 m tolerans) så att filerna blir mindre.
for g in (deso, regso, kommun):
    g["geometry"] = g.geometry.simplify(10, preserve_topology=True)

# Behåll bara de kolumner som är intressanta att visa.
deso = deso[["title", "desokod", "regsokod", "folkmangd", "andel_0_19", "andel_65plus", "yta_km2",
             "inv_per_km2", "fill", "fill-opacity", "stroke", "stroke-width", "geometry"]]
regso = regso[["title", "regsokod", "folkmangd", "inv_per_km2", "fill", "fill-opacity", "stroke", "stroke-width", "geometry"]]

# ---------- 4. Dummylager (påhittade data, koordinater satta för hand) ----------

DUMMY = "DUMMY – påhittade data för test"

hubbar = gpd.GeoDataFrame([
    {"title": "Malmö C", "typ": "stor hubb", "cykelplatser": 1500, "marker-color": "#e41a1c", "marker-size": "large", "geometry": Point(13.0007, 55.6093)},
    {"title": "Triangeln", "typ": "stor hubb", "cykelplatser": 900, "marker-color": "#e41a1c", "marker-size": "large", "geometry": Point(13.0003, 55.5937)},
    {"title": "Hyllie", "typ": "stor hubb", "cykelplatser": 1200, "marker-color": "#e41a1c", "marker-size": "large", "geometry": Point(12.9763, 55.5634)},
    {"title": "Västra Hamnen", "typ": "liten hubb", "cykelplatser": 200, "marker-color": "#377eb8", "marker-size": "medium", "geometry": Point(12.9790, 55.6140)},
    {"title": "Rosengård", "typ": "liten hubb", "cykelplatser": 250, "marker-color": "#377eb8", "marker-size": "medium", "geometry": Point(13.0410, 55.5850)},
    {"title": "Kirseberg", "typ": "liten hubb", "cykelplatser": 150, "marker-color": "#377eb8", "marker-size": "medium", "geometry": Point(13.0360, 55.6080)},
], crs="EPSG:4326")
hubbar["kalla"] = DUMMY

strak_farg = {"befintlig": "#4daf4a", "planerad": "#ff7f00", "utredning": "#984ea3"}
strak = gpd.GeoDataFrame([
    {"title": "Stråk A Centrum–Hyllie", "status": "planerad", "geometry": LineString([(13.0007, 55.6093), (13.0003, 55.5937), (12.9930, 55.5800), (12.9763, 55.5634)])},
    {"title": "Stråk B Västra Hamnen–Rosengård", "status": "utredning", "geometry": LineString([(12.9790, 55.6140), (12.9950, 55.6050), (13.0150, 55.5950), (13.0410, 55.5850)])},
    {"title": "Stråk C Kirseberg–Centrum", "status": "befintlig", "geometry": LineString([(13.0360, 55.6080), (13.0200, 55.6070), (13.0007, 55.6093)])},
], crs="EPSG:4326")
strak["stroke"] = strak["status"].map(strak_farg)
strak["stroke-width"] = 4
strak["kalla"] = DUMMY

omraden = gpd.GeoDataFrame([
    {"title": "Utredningsområde Nyhamnen", "skede": "förstudie", "geometry": Polygon([(12.995, 55.613), (13.010, 55.613), (13.012, 55.620), (12.997, 55.621)])},
    {"title": "Utredningsområde Hyllie centrum", "skede": "detaljplan", "geometry": Polygon([(12.970, 55.558), (12.985, 55.558), (12.985, 55.567), (12.970, 55.567)])},
], crs="EPSG:4326")
omraden["fill"] = "#fdbf6f"
omraden["fill-opacity"] = 0.4
omraden["stroke"] = "#b15928"
omraden["stroke-width"] = 2
omraden["kalla"] = DUMMY

# ---------- 5–6. Skriv filerna ----------

MAPP.mkdir(exist_ok=True)
SCB_KALLA = f"SCB, DeSO/RegSO 2025 (geodata.scb.se) och folkmängd {AR} (tabell BE0101Y/FolkmDesoAldKon)"
lager = [
    ("01-kommungrans.geojson", "Malmö kommungräns", "Sammanslagna DeSO-områden.", SCB_KALLA, kommun),
    ("02-regso.geojson", "RegSO – regionala statistikområden", "Namngivna områden med folkmängd.", SCB_KALLA, regso),
    ("03-deso-befolkning.geojson", "DeSO – befolkning 2025", "Färg = befolkningstäthet (kvintiler). Andel 0–19 och 65+ år.", SCB_KALLA, deso),
    ("04-dummy-mobilitetshubbar.geojson", "Mobilitetshubbar (dummy)", "Punkter. Röd = stor, blå = liten.", DUMMY, hubbar),
    ("05-dummy-cykelstrak.geojson", "Cykelstråk (dummy)", "Linjer. Grön = befintlig, orange = planerad, lila = utredning.", DUMMY, strak),
    ("06-dummy-utredningsomraden.geojson", "Utredningsområden (dummy)", "Ytor.", DUMMY, omraden),
]

alla, lista = [], []
for fil, titel, beskr, kalla, gdf in lager:
    if kalla == SCB_KALLA:
        gdf = gdf.assign(kalla=kalla)
    features = skriv(gdf, fil)
    alla += features
    storlek = (MAPP / fil).stat().st_size
    lista.append({"fil": fil, "titel": titel, "beskrivning": beskr, "kalla": kalla,
                  "antal": len(features), "kb": round(storlek / 1024)})
    print(f"  {fil}: {len(features)} objekt, {storlek / 1024:.0f} kB")

# Alla lager i en fil (geojson.io öppnar en datakälla per länk). Kommun först så att den hamnar underst.
(MAPP / "00-alla-lager.geojson").write_text(
    json.dumps({"type": "FeatureCollection", "features": alla}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
lista.insert(0, {"fil": "00-alla-lager.geojson", "titel": "Alla lager", "beskrivning": "Alla sex lager i en fil.",
                 "kalla": "Se respektive lager", "antal": len(alla),
                 "kb": round((MAPP / "00-alla-lager.geojson").stat().st_size / 1024)})
(MAPP / "lager.json").write_text(json.dumps(lista, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"Klart. Malmö {AR}: {int(deso['folkmangd'].sum())} invånare i {len(deso)} DeSO.")
