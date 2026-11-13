from __future__ import annotations
import hashlib
import json
from pathlib import Path
from urllib import error, request


def _queries_dir() -> Path:
    candidates = [Path("fixtures/queries"), Path(__file__).resolve().parents[1] / "fixtures/queries"]
    for d in candidates:
        if d.is_dir():
            return d
    raise FileNotFoundError("fixtures/queries not found")


def _query_text(name: str) -> str:
    return (_queries_dir() / (name + ".graphql")).read_text()


def _query_hash(name: str) -> str:
    return hashlib.sha256((_queries_dir() / (name + ".graphql")).read_bytes()).hexdigest()


class BudgetExhausted(Exception):
    pass


class Crawler:
    def __init__(self, base: str, budget: int):
        self.base = base.rstrip("/")
        self.remaining = budget
        self.used = 0

    def _post(self, payload: dict) -> dict:
        req = request.Request(
            self.base + "/graphql",
            data=json.dumps(payload).encode(),
            headers={
                "Content-Type": "application/json",
                "X-Budget-Remaining": str(self.remaining),
            },
        )
        try:
            with request.urlopen(req) as resp:
                body = json.loads(resp.read())
        except error.HTTPError as e:
            if e.code == 402:
                raise BudgetExhausted() from e
            raise
        cost = body.get("cost", 0)
        self.remaining -= cost
        self.used += cost
        return body["data"]

    def merchant_root(self) -> dict:
        return self._post({"query": _query_text("MerchantRoot")})

    def orders_page(self, after):
        return self._post({
            "query_hash": _query_hash("OrdersPage"),
            "variables": {"after": after},
        })

    def items_page(self, order_id, after):
        return self._post({
            "query_hash": _query_hash("ItemsPage"),
            "variables": {"orderId": order_id, "after": after},
        })


def _edge_to_order(edge: dict) -> dict:
    node = edge["node"]
    conn = node["items"]
    return {
        "id": node["id"],
        "code": node["code"],
        "items": [e["node"] for e in conn["edges"]],
        "pageInfo": dict(conn["pageInfo"]),
    }


def run_crawl(args) -> int:
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    ckpt_path = Path(args.checkpoint)
    orders_file = out / "orders.jsonl"

    done_ids = set()
    if orders_file.is_file():
        for line in orders_file.read_text().splitlines():
            if line.strip():
                done_ids.add(json.loads(line)["id"])

    crawler = Crawler(args.base, args.budget)

    queue = []
    orders_pi = None
    if ckpt_path.is_file():
        ckpt = json.loads(ckpt_path.read_text())
        orders_pi = ckpt["orders"]
        for o in ckpt.get("pending_orders", []):
            if o["id"] not in done_ids:
                queue.append(o)

    complete = False
    try:
        if orders_pi is None:
            data = crawler.merchant_root()
            conn = data["merchant"]["orders"]
            orders_pi = dict(conn["pageInfo"])
            queue.extend(
                _edge_to_order(e) for e in conn["edges"]
                if e["node"]["id"] not in done_ids
            )

        while True:
            while queue:
                order = queue[0]
                while order["pageInfo"]["hasNextPage"]:
                    data = crawler.items_page(order["id"], order["pageInfo"]["endCursor"])
                    conn = data["merchant"]["order"]["items"]
                    order["items"].extend(e["node"] for e in conn["edges"])
                    order["pageInfo"] = dict(conn["pageInfo"])
                queue.pop(0)
                if order["id"] not in done_ids:
                    items = sorted(order["items"], key=lambda i: i["id"])
                    with orders_file.open("a") as f:
                        f.write(json.dumps({
                            "id": order["id"],
                            "code": order["code"],
                            "items": items,
                        }) + "\n")
                    done_ids.add(order["id"])
            if not orders_pi["hasNextPage"]:
                break
            data = crawler.orders_page(orders_pi["endCursor"])
            conn = data["merchant"]["orders"]
            orders_pi = dict(conn["pageInfo"])
            queue.extend(
                _edge_to_order(e) for e in conn["edges"]
                if e["node"]["id"] not in done_ids
            )
        complete = True
    except BudgetExhausted:
        pass

    checkpoint_saved = False
    if not complete:
        ckpt_path.parent.mkdir(parents=True, exist_ok=True)
        ckpt_path.write_text(json.dumps({
            "orders": orders_pi,
            "items": {o["id"]: o["pageInfo"] for o in queue},
            "pending_orders": queue,
        }, indent=2))
        checkpoint_saved = True
    elif ckpt_path.is_file():
        ckpt_path.unlink()

    report = {
        "budget_used": crawler.used,
        "incomplete": not complete,
        "checkpoint_saved": checkpoint_saved,
    }
    (out / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))
    return 0
