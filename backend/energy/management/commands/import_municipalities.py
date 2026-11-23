"""Import municipality boundaries + population from BKG VG250-EW (GeoPackage).

Expects the download in data/vg250/ (see docs/DATA.md). Safe to re-run: it replaces
all municipalities.
"""

from pathlib import Path

import geopandas as gpd
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from energy.loading import load_municipalities, set_meta


class Command(BaseCommand):
    help = "Import VG250-EW municipalities for the configured Bundesland."

    def add_arguments(self, parser):
        parser.add_argument("--path", help="Path to DE_VG250.gpkg (default: search data/vg250)")

    def handle(self, *args, path=None, **options):
        if path:
            gpkg = Path(path)
        else:
            found = sorted((settings.REPO_ROOT / "data" / "vg250").rglob("*.gpkg"))
            if not found:
                raise CommandError(
                    "No VG250 GeoPackage found. Download vg250-ew_12-31.utm32s.gpkg.ebenen.zip from "
                    "https://daten.gdz.bkg.bund.de/produkte/vg/vg250-ew_ebenen_1231/ and unzip it "
                    "into data/vg250/"
                )
            gpkg = found[0]
        prefix = settings.REGION_LAND_PREFIX
        where = f"AGS LIKE '{prefix}%' AND GF = 4"  # prefix comes from our own settings, not user input

        # GF = 4 means "mit Struktur Land" (land area). GF = 2 rows are the water share
        # (Bodensee) of the same municipalities and would create duplicate keys.
        gem = gpd.read_file(gpkg, layer="vg250_gem", where=where)
        krs = gpd.read_file(gpkg, layer="vg250_krs", where=where, ignore_geometry=True)
        district_names = dict(zip(krs["AGS"], krs["GEN"], strict=True))
        gem = gem.to_crs(4326)  # source is EPSG:25832 (UTM 32N)

        if gem["AGS"].duplicated().any():
            raise CommandError("Duplicate AGS after filtering; check the GF filter.")

        rows = (
            {
                "ags": r.AGS,
                "name": r.GEN,
                "district_ags": r.AGS[:5],
                "district_name": district_names.get(r.AGS[:5], r.AGS[:5]),
                "population": int(r.EWZ) if r.EWZ == r.EWZ else None,
                "wkt": r.geometry.wkt,
            }
            for r in gem.itertuples()
        )
        n = load_municipalities(rows)
        set_meta("population_snapshot", "2025-12-31")
        set_meta("boundaries_source", "BKG VG250-EW 31.12.2025")
        self.stdout.write(self.style.SUCCESS(f"Imported {n} municipalities from {gpkg.name}"))
