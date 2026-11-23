"""Raw-SQL part of the schema: extensions, PostGIS geometry columns, GIST/trigram
indexes and the SELECT-only grants for the read-only role.

We deliberately avoid GeoDjango: the geometry columns are not mapped by the ORM and
are only touched with hand-written, parameterized SQL.
"""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("energy", "0001_initial")]

    operations = [
        migrations.RunSQL(
            "CREATE EXTENSION IF NOT EXISTS postgis; CREATE EXTENSION IF NOT EXISTS pg_trgm;",
            migrations.RunSQL.noop,
        ),
        migrations.RunSQL(
            """
            ALTER TABLE energy_municipality
                ADD COLUMN geom geometry(MultiPolygon, 4326),
                ADD COLUMN geom_simplified geometry(MultiPolygon, 4326);
            CREATE INDEX energy_municipality_geom_gix ON energy_municipality USING GIST (geom);
            CREATE INDEX energy_municipality_name_trgm
                ON energy_municipality USING GIN (name_normalized gin_trgm_ops);

            ALTER TABLE energy_energyunit ADD COLUMN geom geometry(Point, 4326);
            CREATE INDEX energy_energyunit_geom_gix ON energy_energyunit USING GIST (geom);
            -- geography index so ST_DWithin(geom::geography, ...) in metres can use an index
            CREATE INDEX energy_energyunit_geog_gix
                ON energy_energyunit USING GIST ((geom::geography));
            """,
            """
            DROP INDEX IF EXISTS energy_energyunit_geog_gix;
            ALTER TABLE energy_energyunit DROP COLUMN geom;
            ALTER TABLE energy_municipality DROP COLUMN geom_simplified, DROP COLUMN geom;
            """,
        ),
        migrations.RunSQL(
            """
            DO $$ BEGIN
              IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'wattwhere_ro') THEN
                GRANT USAGE ON SCHEMA public TO wattwhere_ro;
                GRANT SELECT ON energy_municipality, energy_energyunit TO wattwhere_ro;
              END IF;
            END $$;
            """,
            migrations.RunSQL.noop,
        ),
    ]
