from copy import deepcopy
DEFAULT_CTX = {
  "client":{"logo_path":None,"name":"","phone":"","country":"","address":""},
  "machine":{"photo_path":None,"name":"","model":"","type":"","serial":""},
  "trainer":{"fullname":"","contacts":"","place":"","participants_count":0,"photo_path":None,"start_date":"","end_date":""},
  "summary":[], "objectives":[], "planning":[],
  "appreciation":[], "conclusion":[], "media_paths":[],
  "attendance_img":None,
  "kpi":{"moy_in":0,"moy_out":0,"evolution":0,"evolution_pct":0,"interpretation":""},
  "charts":{"bars":None,"deltas":None},
  "top_plus":[], "top_moins":[]
}
def with_defaults(ctx: dict | None) -> dict:
    ctx = ctx or {}
    base = deepcopy(DEFAULT_CTX)
    for k, v in ctx.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            base[k].update(v)
        else:
            base[k] = v
    return base