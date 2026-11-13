from __future__ import annotations
import json, hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ORDERS = [{"id": "ORD-1", "code": "C-001", "items": [{"id": "IT-1-1", "sku": "S11", "qty": 11}, {"id": "IT-1-2", "sku": "S12", "qty": 12}, {"id": "IT-1-3", "sku": "S13", "qty": 13}]}, {"id": "ORD-2", "code": "C-002", "items": [{"id": "IT-2-1", "sku": "S21", "qty": 21}, {"id": "IT-2-2", "sku": "S22", "qty": 22}, {"id": "IT-2-3", "sku": "S23", "qty": 23}]}, {"id": "ORD-3", "code": "C-003", "items": [{"id": "IT-3-1", "sku": "S31", "qty": 31}, {"id": "IT-3-2", "sku": "S32", "qty": 32}, {"id": "IT-3-3", "sku": "S33", "qty": 33}]}, {"id": "ORD-4", "code": "C-004", "items": [{"id": "IT-4-1", "sku": "S41", "qty": 41}, {"id": "IT-4-2", "sku": "S42", "qty": 42}, {"id": "IT-4-3", "sku": "S43", "qty": 43}]}, {"id": "ORD-5", "code": "C-005", "items": [{"id": "IT-5-1", "sku": "S51", "qty": 51}, {"id": "IT-5-2", "sku": "S52", "qty": 52}, {"id": "IT-5-3", "sku": "S53", "qty": 53}]}]

def _hash(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()

# loaded from files at serve time
HASH_ONLY = set()
HASH_TO_NAME = {}


def cost_for(kind, n_edges):
    if kind == "root":
        return 1 + 2 * max(n_edges, 1)
    if kind == "orders":
        return 2 * max(n_edges, 1)
    if kind == "items":
        return 3 * max(n_edges, 1)
    return 1


def page_slice(items, first, after, id_key="id"):
    start = 0
    if after:
        start = next((i+1 for i,x in enumerate(items) if x[id_key]==after or x.get("_cursor")==after), 0)
    chunk = items[start:start+first]
    has = start+first < len(items)
    end = chunk[-1][id_key] if chunk else None
    return chunk, has, end


def serve_orders_page(after, first, include_item_preview=True):
    chunk, has, end = page_slice(ORDERS, first, after)
    edges=[]
    for o in chunk:
        item_chunk, ih, ie = page_slice(o["items"], 2, None)
        node={
            "id": o["id"],
            "code": o["code"],
            "items": {
                "edges": [{"cursor": it["id"], "node": dict(it)} for it in item_chunk],
                "pageInfo": {"hasNextPage": ih, "endCursor": ie},
            },
        }
        edges.append({"cursor": o["id"], "node": node})
    return {"merchant": {"orders": {"edges": edges, "pageInfo": {"hasNextPage": has, "endCursor": end}}}}, len(edges), "orders"


class Handler(BaseHTTPRequestHandler):
    def log_message(self,*a):
        return
    def _send(self, st, obj, extra=None):
        body=json.dumps(obj).encode()
        self.send_response(st)
        self.send_header("Content-Type","application/json")
        self.send_header("Content-Length", str(len(body)))
        if extra:
            for k,v in extra.items():
                self.send_header(k,v)
        self.end_headers(); self.wfile.write(body)

    def do_POST(self):
        n=int(self.headers.get("Content-Length") or 0)
        raw=self.rfile.read(n) if n else b"{}"
        try:
            body=json.loads(raw.decode() or "{}")
        except json.JSONDecodeError:
            return self._send(400, {"error":"bad json"})
        q=body.get("query")
        qh=body.get("query_hash")
        variables=body.get("variables") or {}
        name=None
        if qh:
            name=HASH_TO_NAME.get(qh)
            if not name:
                return self._send(400, {"error":"unknown hash"})
        elif q:
            h=_hash(q if q.endswith("\n") else q+"\n")
            # also try exact
            if q in HASH_TO_NAME:
                name=HASH_TO_NAME[q]  # won't happen
            name = HASH_TO_NAME.get(hashlib.sha256(q.encode()).hexdigest()) or HASH_TO_NAME.get(hashlib.sha256((q+"\n").encode()).hexdigest()) or HASH_TO_NAME.get(hashlib.sha256(q.strip("\n").encode()+"\n" if False else q.encode()).hexdigest())
            # require hash for OrdersPage / ItemsPage
            guessed=None
            if qh:
                guessed=None
            if "query OrdersPage" in (q or "") or (name=="OrdersPage"):
                return self._send(400, {"error":"hash-only","operation":"OrdersPage"})
            if "query ItemsPage" in (q or "") or (name=="ItemsPage"):
                return self._send(400, {"error":"hash-only","operation":"ItemsPage"})
            if "query MerchantRoot" in (q or ""):
                name="MerchantRoot"
        else:
            return self._send(400, {"error":"need query or query_hash"})

        remain=self.headers.get("X-Budget-Remaining")
        remain=int(remain) if remain not in (None,"") else 10**9

        if name=="MerchantRoot":
            data, edges, kind = serve_orders_page(None, 2)
            # add merchant id/name
            data["merchant"]["id"]="M-1"
            data["merchant"]["name"]="Northwind"
            cost=1 + 2*max(edges,1)
            # plus preview items: each of 2 orders has 2 item edges -> 3*2*2? docs: items and each item edge cost 3.
            # I'll count items preview: for each order, 3 * max(item_edges,1)
            item_cost=0
            for e in data["merchant"]["orders"]["edges"]:
                ie=len(e["node"]["items"]["edges"])
                item_cost += 3*max(ie,1)
            cost += item_cost
        elif name=="OrdersPage":
            after=variables.get("after")
            data, edges, kind = serve_orders_page(after, 2)
            item_cost=0
            for e in data["merchant"]["orders"]["edges"]:
                ie=len(e["node"]["items"]["edges"])
                item_cost += 3*max(ie,1)
            cost = 2*max(edges,1) + item_cost
        elif name=="ItemsPage":
            oid=variables.get("orderId")
            after=variables.get("after")
            o=next((x for x in ORDERS if x["id"]==oid), None)
            if not o:
                return self._send(404, {"error":"no order"})
            chunk, has, end = page_slice(o["items"], 2, after)
            data={"merchant":{"order":{"id":o["id"],"items":{"edges":[{"cursor":it["id"],"node":dict(it)} for it in chunk],"pageInfo":{"hasNextPage":has,"endCursor":end}}}}}
            cost=3*max(len(chunk),1)
        else:
            return self._send(400, {"error":"unknown operation","name":name})

        if cost>remain:
            return self._send(402, {"error":"budget","cost":cost})
        return self._send(200, {"data": data, "cost": cost})


def serve(host="127.0.0.1", port=8767):
    from pathlib import Path
    global HASH_TO_NAME, HASH_ONLY
    # queries relative to cwd or package
    candidates=[Path("fixtures/queries"), Path(__file__).resolve().parents[1]/"fixtures/queries"]
    qdir=next(d for d in candidates if d.is_dir())
    HASH_TO_NAME={}
    for p in qdir.glob("*.graphql"):
        h=hashlib.sha256(p.read_bytes()).hexdigest()
        HASH_TO_NAME[h]=p.stem
    HASH_ONLY={"OrdersPage","ItemsPage"}
    httpd=ThreadingHTTPServer((host,port), Handler)
    print(f"gqlwalk fixture GraphQL on http://{host}:{port}")
    httpd.serve_forever()

if __name__=="__main__":
    serve()
