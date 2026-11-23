"""Import MaStR units (open-mastr SQLite export) into PostgreSQL/PostGIS.

Steps: (1) optional download via open-mastr (several GB, asks first), (2) stream the
region's units out of SQLite, (3) COPY them into energy_energyunit.

Table/column names below were verified against the real export, see docs/DATA.md.
"""

import os
import re
import sqlite3
from datetime import date

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from energy.loading import load_units, set_meta
from energy.models import Municipality

# technology -> source table in the open-mastr SQLite DB
TABLES = {
    "solar": "EinheitenSolar",
    "wind": "EinheitenWind",
    "biomass": "EinheitenBiomasse",
    "hydro": "EinheitenWasser",
    "storage": "EinheitenStromSpeicher",
}

STATUS_MAP = {
    "In Betrieb": "in_operation",
    "In Planung": "planned",
    "Endgültig stillgelegt": "decommissioned",
}  # everything else (e.g. "Vorübergehend stillgelegt") -> "other"

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}")


def _date(v):
    if not v or not _DATE_RE.match(str(v)):
        return None
    try:
        return date.fromisoformat(str(v)[:10])
    except ValueError:
        return None


def _coords(lat, lon):
    """Return (lat, lon) or (None, None). Rejects values outside a box around Germany."""
    try:
        lat, lon = float(lat), float(lon)
    except (TypeError, ValueError):
        return None, None
    if 46.0 <= lat <= 56.0 and 5.0 <= lon <= 16.0:
        return lat, lon
    return None, None


def _postcode(v):
    s = str(v).strip() if v is not None else ""
    return s[:5] if s[:5].isdigit() and len(s) >= 5 else None


class Command(BaseCommand):
    help = "Download (optional) and import MaStR units for the configured region."

    def add_arguments(self, parser):
        parser.add_argument("--download", action="store_true", help="Run the open-mastr bulk download first")
        parser.add_argument("--yes", action="store_true", help="Don't ask before downloading")
        parser.add_argument("--db", help="Path to open-mastr.db (default: <OUTPUT_PATH>/data/sqlite/open-mastr.db)")

    def _db_path(self, opt):
        if opt:
            return opt
        out = os.environ.get("OUTPUT_PATH", "./data/open-mastr")
        out = out if os.path.isabs(out) else str(settings.REPO_ROOT / out)
        return os.path.join(out, "data", "sqlite", "open-mastr.db")

    def handle(self, *args, db=None, download=False, yes=False, **options):
        path = self._db_path(db)
        if download or not os.path.exists(path):
            if not yes:
                ans = input(
                    "The MaStR bulk export is SEVERAL GB (about 9 GB on disk after parsing) and takes "
                    "~30 minutes. Download now? [y/N] "
                )
                if ans.strip().lower() != "y":
                    raise CommandError("Aborted. No data downloaded.")
            out = os.path.dirname(os.path.dirname(os.path.dirname(path)))
            os.environ["OUTPUT_PATH"] = out
            from open_mastr import Mastr

            Mastr().download(method="bulk", data=list(TABLES))
        if not os.path.exists(path):
            raise CommandError(f"MaStR database not found at {path}")

        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        con.row_factory = sqlite3.Row
        known_ags = set(Municipality.objects.values_list("ags", flat=True))
        if not known_ags:
            raise CommandError("No municipalities loaded. Run import_municipalities first.")

        # Storage capacity (kWh) lives in a separate table, linked by unit number.
        kwh = {}
        for r in con.execute(
            "SELECT VerknuepfteEinheitenMastrNummern u, NutzbareSpeicherkapazitaet k FROM AnlagenStromSpeicher"
        ):
            if r["u"] and r["k"] is not None:
                kwh[r["u"]] = r["k"]

        stats = {t: {"rows": 0, "coords": 0, "no_ags": 0} for t in TABLES}
        seen: set[str] = set()

        def rows():
            prefix, region = settings.REGION_LAND_PREFIX, settings.REGION_NAME
            for tech, table in TABLES.items():
                extra = ", ArtDerSolaranlage AS loc" if tech == "solar" else ", NULL AS loc"
                cur = con.execute(
                    f"""SELECT EinheitMastrNummer id, EinheitBetriebsstatus st, Nettonennleistung net,
                               Bruttoleistung gross, Inbetriebnahmedatum comm,
                               DatumEndgueltigeStilllegung decomm, Gemeindeschluessel ags,
                               Postleitzahl plz, Breitengrad lat, Laengengrad lon {extra}
                        FROM {table}
                        WHERE Bundesland = ? OR Gemeindeschluessel LIKE ?""",  # noqa: S608 (table names are constants)
                    (region, f"{prefix}%"),
                )
                s = stats[tech]
                for r in cur:
                    if r["id"] in seen:
                        continue
                    seen.add(r["id"])
                    lat, lon = _coords(r["lat"], r["lon"])
                    ags = r["ags"] if r["ags"] in known_ags else None
                    s["rows"] += 1
                    s["coords"] += lat is not None
                    s["no_ags"] += ags is None
                    status_raw = r["st"] or ""
                    yield (
                        r["id"], tech, status_raw, STATUS_MAP.get(status_raw, "other"),
                        r["net"], r["gross"], kwh.get(r["id"]) if tech == "storage" else None,
                        _date(r["comm"]), _date(r["decomm"]), ags, _postcode(r["plz"]),
                        lat, lon, r["loc"],
                    )  # fmt: skip

        total = load_units(rows())
        dl = con.execute("SELECT DatumDownload FROM EinheitenSolar LIMIT 1").fetchone()
        if dl and dl[0]:
            d = str(dl[0])
            set_meta("snapshot_date", f"{d[:4]}-{d[4:6]}-{d[6:8]}")
        set_meta("source", "Marktstammdatenregister (Bundesnetzagentur), dl-de/by-2-0")

        self.stdout.write(self.style.SUCCESS(f"Imported {total:,} units"))
        for t, s in stats.items():
            pct = 100 * s["coords"] / s["rows"] if s["rows"] else 0
            self.stdout.write(
                f"  {t:8s} {s['rows']:>9,} units | with coordinates {s['coords']:>8,} ({pct:.1f}%) "
                f"| unmatched municipality key {s['no_ags']:,}"
            )
