# gqlwalk

沿着供应商后台的 GraphQL connection 往下收数。查询有费用上限，部分操作必须走持久化查询哈希，超限时要把未走完的游标写入检查点。

```
python -m gqlwalk site --port 8767
python -m gqlwalk crawl --base http://127.0.0.1:8767 --budget 40 --out <out> --checkpoint <ckpt>
python -m gqlwalk verify --out <out> --expect fixtures/expected/tree.json
```
