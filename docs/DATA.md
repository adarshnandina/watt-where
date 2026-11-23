# Data

## Sources and licences

| Dataset | Used for | Licence / attribution |
|---|---|---|
| Marktstammdatenregister (MaStR), Bundesnetzagentur, via `open-mastr` bulk export | Generation and storage units | dl-de/by-2-0, "Datenquelle: Marktstammdatenregister (Bundesnetzagentur), dl-de/by-2-0" |
| BKG VG250-EW (31.12.2025) | Municipality boundaries, AGS, population (`EWZ`) | © BKG (2025), dl-de/by-2-0 |
| OpenStreetMap | Map tiles (frontend) | © OpenStreetMap contributors (ODbL) |

**Snapshots in this build:** MaStR export dated **2026-11-23** (`DatumDownload`); VG250-EW population/boundaries as of **2025-12-31**. Both are stored in the `energy_datameta` table and shown by `/api/health`.

## VG250-EW

- Downloaded from `https://daten.gdz.bkg.bund.de/produkte/vg/vg250-ew_ebenen_1231/2025/`, file `vg250-ew_12-31.utm32s.gpkg.ebenen.zip` (70 MB, MD5 checked). The 2025 folder has no WGS84 (`geo84`) variant, so we use the GeoPackage in EPSG:25832 and reproject to EPSG:4326 on import.
- Layers used: `vg250_gem` (municipalities) and `vg250_krs` (district names).
- **Geofactor (`GF`)**: the download's own code table (`v_werte_gf`) says `4 = mit Struktur Land` (land area) and `2 = mit Struktur Gewässer`. In Baden-Württemberg 6 municipalities on Lake Constance have an extra `GF=2` row (water share). We keep **`GF = 4` only**, giving unique AGS keys. Verified: 1,103 rows, 1,103 distinct AGS.
- Result: **1,103 municipalities**, all with geometry and population (total 11.24 M). Freiburg im Breisgau: AGS `08311000`, 238,299 inhabitants, 153.8 km².
- Derived in SQL: area (`ST_Area` on geography), centroid (`ST_PointOnSurface`), simplified geometry (`ST_SimplifyPreserveTopology`, tolerance 0.0005°).

## MaStR (open-mastr)

`open-mastr` (bulk method) wrote a ~7 GB SQLite DB to `data/open-mastr/data/sqlite/open-mastr.db`. It contains raw tables (German column names) and views (`solar_extended`, ...). **We read the raw tables** since they hold the columns we need directly:

| Technology | Table | Rows (national) |
|---|---|---|
| solar | `EinheitenSolar` | 6.69 M |
| wind | `EinheitenWind` | 44 k |
| biomass | `EinheitenBiomasse` | 24 k |
| hydro | `EinheitenWasser` | 8.8 k |
| storage | `EinheitenStromSpeicher` (+ `AnlagenStromSpeicher` for kWh) | 2.97 M |

### Column mapping

| Our column | MaStR column | Notes |
|---|---|---|
| `mastr_id` | `EinheitMastrNummer` | |
| `status_raw` / `status` | `EinheitBetriebsstatus` | `In Betrieb`→in_operation, `In Planung`→planned, `Endgültig stillgelegt`→decommissioned, `Vorübergehend stillgelegt`→other |
| `net_capacity_kw` | `Nettonennleistung` | kW |
| `gross_capacity_kw` | `Bruttoleistung` | kW |
| `commissioning_date` | `Inbetriebnahmedatum` | ISO text `YYYY-MM-DD`. Null for planned units |
| `decommissioning_date` | `DatumEndgueltigeStilllegung` | |
| `municipality_id` | `Gemeindeschluessel` | 8-digit text; set to NULL if not in VG250 2025 |
| `postcode` | `Postleitzahl` | |
| `lat` / `lon` | `Breitengrad` / `Laengengrad` | rejected if outside lat 46–56, lon 5–16 |
| `solar_location_type` | `ArtDerSolaranlage` | Gebäudesolaranlage, Freiflächensolaranlage, Steckerfertige Solaranlage (Balkonkraftwerk), Sonstige |
| `storage_capacity_kwh` | `AnlagenStromSpeicher.NutzbareSpeicherkapazitaet` | joined via `VerknuepfteEinheitenMastrNummern` = unit id |

Region filter: `Bundesland = 'Baden-Württemberg' OR Gemeindeschluessel LIKE '08%'`.
The bulk export contains no `Lage` column; `ArtDerSolaranlage` is the closest equivalent.

### Import results (BW)

| Technology | Units | With coordinates | Unmatched municipality key |
|---|---|---|---|
| solar | 1,062,162 | 42,422 (4.0%) | 103 |
| wind | 1,324 | 1,202 (90.8%) | 0 |
| biomass | 2,853 | 2,705 (94.8%) | 0 |
| hydro | 1,974 | 1,153 (58.4%) | 0 |
| storage | 466,548 | 1,221 (0.3%) | 18 |
| **total** | **1,534,861** | | |

Import time: ~35 s (COPY). The re-run is idempotent (truncate + load in one transaction).

## Caveats

- **Coordinates:** only 4% of solar and 0.3% of storage units have public coordinates (privacy). Municipality aggregates are complete; map points are not. The agent must say so for point-based answers.
- **Capacity:** default is *net* capacity (`Nettonennleistung`) of units *in operation*.
- **Unmatched keys:** 121 units carry a municipality key that doesn't exist in VG250 2025 (e.g. municipality mergers or missing keys). They count in region-wide totals but not in any municipality.
- **Storage capacity (kWh)** exists only where an `AnlagenStromSpeicher` record is linked.
- **Per-capita figures** use the population at 31.12.2025, not the population at the time of commissioning.
- Balkonkraftwerke (plug-in solar, ~219k BW units) are included in solar unit counts; they add little capacity.
