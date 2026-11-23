from django.db import models


class Municipality(models.Model):
    ags = models.CharField(max_length=8, primary_key=True)  # official 8-digit key
    name = models.CharField(max_length=200, db_index=True)
    name_normalized = models.CharField(max_length=200, db_index=True)  # lowercase, umlauts folded
    district_ags = models.CharField(max_length=5, db_index=True)
    district_name = models.CharField(max_length=200)
    population = models.IntegerField(null=True)
    area_km2 = models.FloatField(null=True)
    centroid_lat = models.FloatField()
    centroid_lon = models.FloatField()
    # geometry columns are added in migration 0002 via RunSQL (not mapped by Django):
    #   geom geometry(MultiPolygon, 4326), geom_simplified geometry(MultiPolygon, 4326)

    def __str__(self):
        return f"{self.name} ({self.ags})"


class EnergyUnit(models.Model):
    mastr_id = models.CharField(max_length=32, primary_key=True)
    technology = models.CharField(max_length=20, db_index=True)  # solar|wind|biomass|hydro|storage
    status_raw = models.CharField(max_length=100)
    status = models.CharField(max_length=20, db_index=True)  # in_operation|planned|decommissioned|other
    net_capacity_kw = models.FloatField(null=True)
    gross_capacity_kw = models.FloatField(null=True)
    storage_capacity_kwh = models.FloatField(null=True)
    commissioning_date = models.DateField(null=True, db_index=True)
    decommissioning_date = models.DateField(null=True)
    municipality = models.ForeignKey(
        Municipality, null=True, on_delete=models.SET_NULL, db_constraint=False
    )
    postcode = models.CharField(max_length=5, null=True)
    lat = models.FloatField(null=True)
    lon = models.FloatField(null=True)
    solar_location_type = models.CharField(max_length=100, null=True)
    # geometry column added via RunSQL in 0002: geom geometry(Point, 4326), nullable

    class Meta:
        indexes = [models.Index(fields=["municipality", "technology", "status"])]


class DataMeta(models.Model):
    """Small key/value table: data snapshot dates etc. (shown by /api/health)."""

    key = models.CharField(max_length=50, primary_key=True)
    value = models.CharField(max_length=200)
