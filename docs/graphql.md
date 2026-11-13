# 夹具 GraphQL

`POST /graphql` 接受 JSON：`{"query": "..."}` 或 `{"query_hash": "<sha256 hex of the exact query string>"}`。下列操作 **只接受 query_hash**，直接提交 query 文本会 400：`OrdersPage`、`ItemsPage`。`MerchantRoot` 可以直接发 query。哈希算法是对查询字符串的 UTF-8 字节做 sha256，十六进制小写。

仓库里 `fixtures/queries/` 放了这三条查询原文，`fixtures/query-hashes.json` 是对应 sha256。hash 必须按文件原文字节计算。OrdersPage 使用变量 `$after`，ItemsPage 使用 `$orderId` 和 `$after`，在 JSON body 的 `variables` 里传。

## 查询费用

每个字段有费用，写在响应扩展里也对不上账，要以夹具规则为准：

- `merchant`：1
- `orders` 或 `orders` 的每一条边：2（每次请求按返回的 edge 数计，空页计 2）
- `items` 及每条 item 边：3

一次 HTTP 请求的费用是上述之和。请求头 `X-Budget-Remaining` 告诉服务器当前还能花多少；缺省视为无限，但 `crawl --budget 40` 必须自己维护剩余预算，并把剩余值传到这个头。若本次查询费用会超过剩余预算，服务器返回 402 和 `{"error":"budget","cost":N}`，不返回数据。此时客户端应把已经落盘的树留下，并在 checkpoint 写下每个未完成 connection 的 `endCursor` 和 `hasNextPage`。

`--budget 40` 不够一次收完整个树（完整收完大约要 70+），所以第一次 crawl 必须部分完成并写出 checkpoint；用同一 checkpoint 再跑一次、把 budget 仍当作这一趟的 40（或更大）时，应从断点继续，不能把已写过的边复制一份。

为了让第一次就被截断，请按这个遍历顺序：先拉 merchant 根，再按订单 cursor 往下走，每个订单先把它的 items 全部翻完，再进入下一张订单。不要先把所有订单翻完再回头拉 items。

## 形状

MerchantRoot：

```
query MerchantRoot {
  merchant { id name orders(first:2, after:null) { edges { cursor node { id code items(first:2, after:null) { edges { cursor node { id sku qty } } pageInfo { hasNextPage endCursor } } } } pageInfo { hasNextPage endCursor } } }
}
```

OrdersPage / ItemsPage 用 after 继续翻页，查询原文见 fixtures/queries/。夹具里有 5 张订单，每张 3 个 item。

## 输出

`--out/orders.jsonl` 一行一张订单，含 `id,code,items`（items 为 `{id,sku,qty}` 数组，按 id 排序）。`--out/report.json` 含 `budget_used`、`incomplete`（布尔）、`checkpoint_saved`（布尔）。
