import argparse
def main(argv=None):
    p=argparse.ArgumentParser(prog="gqlwalk")
    sub=p.add_subparsers(dest="cmd", required=True)
    s=sub.add_parser("site")
    s.add_argument("--port", type=int, default=8767)
    s.add_argument("--host", default="127.0.0.1")
    c=sub.add_parser("crawl")
    c.add_argument("--base", required=True)
    c.add_argument("--budget", type=int, required=True)
    c.add_argument("--out", required=True)
    c.add_argument("--checkpoint", required=True)
    v=sub.add_parser("verify")
    v.add_argument("--out", required=True)
    v.add_argument("--expect", required=True)
    args=p.parse_args(argv)
    if args.cmd=="site":
        from gqlwalk.site import serve
        serve(args.host, args.port); return 0
    if args.cmd=="crawl":
        from gqlwalk.crawl import run_crawl
        return run_crawl(args)
    if args.cmd=="verify":
        from gqlwalk.verify import run_verify
        return run_verify(args)
    return 2
if __name__=="__main__":
    raise SystemExit(main())
