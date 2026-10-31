"""Rewrite argaam_ids.json from Argaam's live company list: uv run python update_argaam_ids.py"""
import json

from src import news as t

ids = t.argaam_list(t.fetch(t.ARGAAM))
assert ids, "no Main market rows; Argaam's page layout may have changed"  # don't wipe the map
t.ARGAAM_IDS.write_text(json.dumps(ids, indent=1, sort_keys=True) + "\n")
print(len(ids), "symbols")
