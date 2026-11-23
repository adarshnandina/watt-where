"""Load a small, deterministic, SYNTHETIC dataset for development and tests.

Nothing here is real: five rectangular "municipalities" around Freiburg (names and keys
are borrowed for realism, the shapes are boxes) and ~200 randomly generated units from a
fixed seed. Never use these numbers as facts.
"""

import random
from datetime import date

from django.core.management.base import BaseCommand

from energy.loading import load_municipalities, load_units, set_meta

# (ags, name, district_ags, district_name, population, lon_min, lat_min, lon_max, lat_max)
SAMPLE_MUNICIPALITIES = [
    ("08311000", "Freiburg im Breisgau", "08311", "Freiburg im Breisgau", 230000, 7.75, 47.95, 7.93, 48.05),
    ("08315001", "Gundelfingen", "08315", "Breisgau-Hochschwarzwald", 12000, 7.93, 48.00, 8.03, 48.08),
    ("08315002", "Merzhausen", "08315", "Breisgau-Hochschwarzwald", 5000, 7.75, 47.90, 7.85, 47.95),
    ("08315003", "Bad Krozingen", "08315", "Breisgau-Hochschwarzwald", 19000, 7.55, 47.85, 7.75, 47.95),
    ("08316001", "Emmendingen", "08316", "Emmendingen", 27000, 7.80, 48.10, 7.95, 48.20),
]  # fmt: skip

TECH_WEIGHTS = {"solar": 0.6, "wind": 0.08, "biomass": 0.08, "hydro": 0.06, "storage": 0.18}


def _box(lon0, lat0, lon1, lat1) -> str:
    return f"POLYGON(({lon0} {lat0},{lon1} {lat0},{lon1} {lat1},{lon0} {lat1},{lon0} {lat0}))"


def generate_units(seed: int = 42, n: int = 200) -> list[tuple]:
    rng = random.Random(seed)
    techs = list(TECH_WEIGHTS)
    weights = list(TECH_WEIGHTS.values())
    rows = []
    for i in range(n):
        ags, _, _, _, _, lo0, la0, lo1, la1 = rng.choice(SAMPLE_MUNICIPALITIES)
        tech = rng.choices(techs, weights)[0]
        status_raw, status = rng.choices(
            [("In Betrieb", "in_operation"), ("In Planung", "planned"),
             ("Endgültig stillgelegt", "decommissioned")],
            [0.85, 0.05, 0.10],
        )[0]  # fmt: skip
        cap = {
            "solar": rng.choice([5, 8, 10, 30, 100, 750]),
            "wind": rng.choice([2000, 3000, 4500]),
            "biomass": rng.choice([100, 250, 500]),
            "hydro": rng.choice([20, 150, 800]),
            "storage": rng.choice([5, 8, 1000]),
        }[tech]
        commissioned = date(rng.randint(2005, 2024), rng.randint(1, 12), rng.randint(1, 28))
        decom = date(min(commissioned.year + 10, 2024), 6, 1) if status == "decommissioned" else None
        has_coords = rng.random() < 0.35 if tech == "solar" else rng.random() < 0.9
        lat = round(rng.uniform(la0, la1), 6) if has_coords else None
        lon = round(rng.uniform(lo0, lo1), 6) if has_coords else None
        rows.append((
            f"SEE{i:09d}", tech, status_raw, status, float(cap), cap * 1.05,
            cap * 2.0 if tech == "storage" else None, commissioned, decom, ags,
            "79100", lat, lon, rng.choice(["Dach", "Freifläche"]) if tech == "solar" else None,
        ))  # fmt: skip
    return rows


class Command(BaseCommand):
    help = "Load the small synthetic sample dataset (dev/tests only)."

    def handle(self, *args, **options):
        n_m = load_municipalities(
            {
                "ags": a, "name": n, "district_ags": d, "district_name": dn,
                "population": p, "wkt": _box(x0, y0, x1, y1),
            }
            for a, n, d, dn, p, x0, y0, x1, y1 in SAMPLE_MUNICIPALITIES
        )  # fmt: skip
        n_u = load_units(generate_units())
        set_meta("source", "SYNTHETIC SAMPLE DATA")
        set_meta("snapshot_date", "synthetic")
        self.stdout.write(self.style.SUCCESS(f"Loaded {n_m} municipalities and {n_u} synthetic units"))
