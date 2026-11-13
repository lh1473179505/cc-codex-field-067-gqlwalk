第一次 --budget 40 的 crawl 应 incomplete=true 且写出 checkpoint。随后用同一 checkpoint 再跑（预算仍由命令行给出）应补全。最终 verify 对照 fixtures/expected/tree.json 比较全部 5 张订单及其 3 个 item，行顺序无关。
