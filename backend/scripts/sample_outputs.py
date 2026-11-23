"""Print sample output of every tool for Freiburg im Breisgau against the real data.
Run: uv run python scripts/sample_outputs.py"""

import json
import os
import sys

import django

sys.path.insert(0, ".")
os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
django.setup()
from energy.tools import call_tool  # noqa: E402


def show(name, args):
    r, ms = call_tool(name, args)
    print(f"\n### {name} {json.dumps(args)[:100]}  [{ms} ms]  ok={r.ok}\nSUMMARY: {r.summary}")
    print("LLM:", json.dumps(r.llm_content, ensure_ascii=False)[:900])
    print("DISPLAY:", [(d["kind"], len(json.dumps(d))) for d in r.display])


show("find_municipality", {"query": "Freiburg"})
show("find_municipality", {"query": "Freiberg"})
show("capacity_summary", {"area": "08311000"})
show("capacity_summary", {"area": "08315"})
show("capacity_summary", {"area": "region", "technologies": ["wind"]})
show("rank_municipalities", {"metric": "kw_per_capita", "technology": "solar", "min_population": 1000})
show("units_near", {"municipality_ags": "08311000", "radius_km": 25, "technology": "wind"})
show("capacity_timeseries", {"area": "08311000", "technologies": ["storage"], "from_year": 2015})
show("run_readonly_sql", {"query": "select technology, count(*) from energy_energyunit group by 1"})
show("run_readonly_sql", {"query": "select * from energy_municipality limit 1"})
show("run_readonly_sql", {"query": "select pg_read_file('/etc/passwd')"})
show("capacity_summary", {"area": "xx"})
