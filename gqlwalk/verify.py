from __future__ import annotations
import json
from pathlib import Path

def rows(path):
    if not Path(path).is_file():
        return []
    return [json.loads(l) for l in Path(path).read_text().splitlines() if l.strip()]

def run_verify(args) -> int:
    out=Path(args.out)
    exp=json.loads(Path(args.expect).read_text())
    got={r["id"]: r for r in rows(out/"orders.jsonl")}
    errors=[]
    exp_o={r["id"]: r for r in exp["orders"]}
    if set(got)!=set(exp_o):
        errors.append(f"order ids extra={sorted(set(got)-set(exp_o))} missing={sorted(set(exp_o)-set(got))}")
    for oid,e in exp_o.items():
        g=got.get(oid)
        if not g: continue
        if g.get("code")!=e["code"]:
            errors.append(f"{oid} code {g.get('code')}")
        gi={i["id"]: i for i in g.get("items") or []}
        ei={i["id"]: i for i in e["items"]}
        if set(gi)!=set(ei):
            errors.append(f"{oid} items {sorted(gi)} != {sorted(ei)}")
            continue
        for iid,iv in ei.items():
            if gi[iid].get("sku")!=iv["sku"] or gi[iid].get("qty")!=iv["qty"]:
                errors.append(f"{iid} {gi[iid]} != {iv}")
    if errors:
        print("verify failed:")
        for e in errors:
            print(" -", e)
        return 1
    print("verify ok")
    return 0
