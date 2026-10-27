# geojson-workshop — Malmö-lager för geojson.io

Test (2026-10-27): visa egna GeoJSON-lager på en workshop via geojson.io, med länk och QR-kod per lager. Deltagarna öppnar lagret i webbläsaren, kan rita och ändra, och sparar en egen kopia via geojson.io:s Save-meny. Inget konto behövs.

## Innehåll

| Fil | Innehåll |
|---|---|
| `index.html` | Workshop-sida: ett kort per lager med geojson.io-länk, QR-kod (klicka för helskärm) och nedladdning |
| `lager/01-kommungrans.geojson` | Malmö kommungräns (sammanslagna DeSO) |
| `lager/02-regso.geojson` | 91 RegSO-områden med namn och folkmängd |
| `lager/03-deso-befolkning.geojson` | 209 DeSO-områden: folkmängd 2025, andel 0–19 och 65+ år, invånare/km². Färg efter täthet (kvintiler) |
| `lager/04–06-dummy-*.geojson` | Påhittade data: mobilitetshubbar (punkter), cykelstråk (linjer), utredningsområden (ytor) |
| `lager/00-alla-lager.geojson` | Alla lager i en fil |
| `lager/lager.json` | Lista som `index.html` läser |
| `bygg_lager.py` | Hämtar SCB-data och bygger om alla lager (kräver geopandas) |

## Testat 2026-10-27

Headless Chromium mot riktiga geojson.io, med GitHub simulerat (filerna serverades från disken). Workshop-sidan visar 7 kort med QR-koder, och geojson.io läser och ritar lagren med färgerna från filerna. Se `docs/`. Inte testat: riktig GitHub Pages, mobil, AFRY-nätet.

## Källor och licens

- DeSO och RegSO 2025: SCB:s WFS `geodata.scb.se/geoserver/stat/wfs` (lager `stat:DeSO_2025`, `stat:RegSO_2025`).
- Folkmängd 31 dec 2025 per DeSO: SCB:s statistikdatabas, tabell `BE0101Y/FolkmDesoAldKon`.
- SCB anger CC0 för sina öppna data. Källa: SCB.
- Dummylagren är påhittade. Koordinaterna är satta för hand och ungefärliga.
- Färger och stil följer simplestyle-spec (`fill`, `stroke`, `marker-color` osv.), som geojson.io läser.

## Lägga upp repot på ett GitHub-konto (t.ex. jobbkontot)

Gå till mappen och kör (byt `<konto>`):

```
git init -b main && git add . && git commit -m "Workshop-lager Malmö"
gh repo create geojson-workshop-test --public --source . --push
gh api -X POST repos/<konto>/geojson-workshop-test/pages -f "source[branch]=main" -f "source[path]=/"
```

Efter 1–2 minuter finns sidan på `https://<konto>.github.io/geojson-workshop-test/`. Länkarna på sidan pekar då automatiskt på rätt filer.

Repot måste vara publikt, annars kan geojson.io inte läsa filerna. Om jobbets GitHub-organisation inte tillåter publika repon eller Pages fungerar inte upplägget där. Lägg då bara öppna data och dummydata i repot, aldrig kund- eller projektdata.

## Bygga om lagren

```
~/Workspaces/geospatial/.venv/bin/python bygg_lager.py
```

Byt `KOMMUN` i skriptet för en annan kommun.

## Begränsningar

- geojson.io läser bara WGS84 (lon/lat). Skriptet projicerar om från SWEREF 99 TM.
- En länk = en fil. Därför finns `00-alla-lager.geojson`.
- Länkformatet måste vara exakt `https://geojson.io/#data=data:text/x-url,<url-kodad adress>`. Testat 2026-10-27: `&map=` efter adressen blir en del av filnamnet, och `map=` före `data=` gör att datat inte laddas. geojson.io zoomar själv till datat.
- Deltagarnas ändringar sparas inte centralt. Varje person exporterar sin egen version.
- QR-koderna kräver att `cdn.jsdelivr.net` inte är blockerat. Annars visas bara länkarna.
