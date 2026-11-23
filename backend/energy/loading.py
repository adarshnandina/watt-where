"""Bulk-loading helpers shared by seed_sample and the real importers.

Both loaders are idempotent: they TRUNCATE and reload inside one transaction.
Units are streamed in with COPY (minutes, not hours, for ~1M rows).
"""

from collections.abc import Iterable

from django.db import connection, transaction

from .textnorm import normalize_name

UNIT_COLUMNS = [
    "mastr_id", "technology", "status_raw", "status", "net_capacity_kw",
    "gross_capacity_kw", "storage_capacity_kwh", "commissioning_date",
    "decommissioning_date", "municipality_id", "postcode", "lat", "lon",
    "solar_location_type",
]  # fmt: skip


def load_municipalities(rows: Iterable[dict]) -> int:
    """rows: ags, name, district_ags, district_name, population, wkt (EPSG:4326 polygons).

    Centroid, area and the simplified geometry are derived in SQL from the full geometry.
    """
    with transaction.atomic(), connection.cursor() as cur:
        cur.execute("TRUNCATE energy_municipality")
        n = 0
        for r in rows:
            cur.execute(
                """
                INSERT INTO energy_municipality
                  (ags, name, name_normalized, district_ags, district_name, population,
                   centroid_lat, centroid_lon, geom)
                VALUES (%s,%s,%s,%s,%s,%s,0,0,
                        ST_Multi(ST_CollectionExtract(ST_MakeValid(ST_GeomFromText(%s, 4326)), 3)))
                """,
                [
                    r["ags"], r["name"], normalize_name(r["name"]), r["district_ags"],
                    r["district_name"], r.get("population"), r["wkt"],
                ],
            )  # fmt: skip
            n += 1
        cur.execute(
            """
            UPDATE energy_municipality SET
              area_km2 = ST_Area(geom::geography) / 1e6,
              centroid_lat = ST_Y(ST_PointOnSurface(geom)),
              centroid_lon = ST_X(ST_PointOnSurface(geom)),
              geom_simplified = ST_Multi(ST_CollectionExtract(
                  ST_MakeValid(ST_SimplifyPreserveTopology(geom, 0.0005)), 3))
            """
        )
    return n


def load_units(rows: Iterable[tuple]) -> int:
    """rows: tuples in UNIT_COLUMNS order. Truncate + COPY + derive point geometry."""
    cols = ", ".join(UNIT_COLUMNS)
    n = 0
    with transaction.atomic(), connection.cursor() as cur:
        cur.execute("TRUNCATE energy_energyunit")
        with cur.cursor.copy(f"COPY energy_energyunit ({cols}) FROM STDIN") as copy:
            for row in rows:
                copy.write_row(row)
                n += 1
        cur.execute(
            """
            UPDATE energy_energyunit
            SET geom = ST_SetSRID(ST_MakePoint(lon, lat), 4326)
            WHERE lat IS NOT NULL AND lon IS NOT NULL
            """
        )
        cur.execute("ANALYZE energy_energyunit")
    return n


def set_meta(key: str, value: str) -> None:
    from .models import DataMeta

    DataMeta.objects.update_or_create(key=key, defaults={"value": value})
