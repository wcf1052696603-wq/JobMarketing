# -*- coding: utf-8 -*-
"""命令行入口：collect / analyze / report / deliver / cleanup / run-all。"""
import argparse
import csv
import json
import os
import random
import sys
import time

from . import browser as B
from . import config as C
from . import lipin as L
from . import match as M
from . import report as R


def _paths(cfg):
    root = os.getcwd()
    return {
        "data_dir": os.path.join(root, cfg["paths"]["data_dir"]),
        "output_dir": os.path.join(root, cfg["paths"]["output_dir"]),
        "profile": os.path.join(root, cfg["paths"]["browser_profile"]),
    }


def _ensure_dirs(cfg):
    p = _paths(cfg)
    os.makedirs(p["data_dir"], exist_ok=True)
    os.makedirs(p["output_dir"], exist_ok=True)
    return p


def _tiers(cfg, override=None):
    return override.split(",") if override else cfg["deliver"]["tiers"]


def cmd_collect(cfg, args):
    p = _ensure_dirs(cfg)
    raw = {}
    with B.Session(cfg["browser"]["port"], p["profile"], L.HOST) as s:
        d = L.load_dict(s.page)
        edu = d["edu"].get(cfg["search"].get("edu_level_name") or "")
        cpt = d["company_type"].get(cfg["search"].get("company_type_name") or "")
        for kw in cfg["search"]["keywords"]:
            total, got = None, 0
            for pg_no in range(1, cfg["search"]["max_pages_per_keyword"] + 1):
                items, total = L.search(s.page, kw, edu, cpt, pg_no, cfg["search"]["page_size"])
                if not items:
                    break
                for it in items:
                    raw.setdefault(it["id"], it)
                got += len(items)
                time.sleep(0.4)
                if total and got >= total:
                    break
            print("[collect] %-8s total=%-7s 累计去重=%d" % (kw, total, len(raw)), flush=True)
    out = {"collected_at": time.strftime("%Y-%m-%d %H:%M"), "items": list(raw.values())}
    path = os.path.join(p["data_dir"], "jobs_raw.json")
    json.dump(out, open(path, "w", encoding="utf-8"), ensure_ascii=False)
    print("[collect] 保存 %d 条 -> %s" % (len(raw), path))
    return path


def cmd_analyze(cfg, args):
    p = _ensure_dirs(cfg)
    raw = json.load(open(os.path.join(p["data_dir"], "jobs_raw.json"), encoding="utf-8"))
    f = cfg["filters"]
    sc = cfg["scoring"]
    sc = dict(sc)
    sc["_core"] = set(f.get("core_disciplines") or [])
    sc["_near"] = set(f.get("near_disciplines") or [])
    sc["_unit_url"] = L.unit_url

    kept = M.filter_items(raw["items"], f)
    for it in kept:
        it["_url"] = L.position_url(it["id"])
    units = M.aggregate(kept, sc, f, cfg["job_types"], cfg.get("keep_title_keywords") or [])
    t1, t2, t3 = M.split_tiers(units, sc)

    short = {
        "source": "理聘 lipind.com",
        "title": cfg["report"]["title"],
        "collected_at": raw.get("collected_at", time.strftime("%Y-%m-%d %H:%M")),
        "stats": {"raw_positions": len(raw["items"]), "matched_positions": len(units and kept),
                  "units": len(units), "tier1": len(t1), "tier2": len(t2), "tier3": len(t3)},
        "tier1": t1, "tier2": t2, "tier3": t3,
    }
    short["stats"]["matched_positions"] = len(kept)
    path = os.path.join(p["data_dir"], "shortlist.json")
    json.dump(short, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("[analyze] 岗位 %d -> 匹配 %d；单位 %d（首选 %d / 可投 %d / 冲刺 %d）"
          % (len(raw["items"]), len(kept), len(units), len(t1), len(t2), len(t3)))
    return path


def cmd_report(cfg, args):
    p = _ensure_dirs(cfg)
    short = json.load(open(os.path.join(p["data_dir"], "shortlist.json"), encoding="utf-8"))
    f = cfg["filters"]
    bits = []
    if cfg["search"].get("edu_level_name"):
        bits.append(cfg["search"]["edu_level_name"])
    if cfg["search"].get("company_type_name"):
        bits.append(cfg["search"]["company_type_name"])
    if f.get("include_city_names"):
        bits.append("限定 %d 个城市" % len(f["include_city_names"]))
    if f.get("exclude_title_keywords"):
        bits.append("排除：" + "/".join(f["exclude_title_keywords"]))
    html = os.path.join(p["output_dir"], "岗位投递清单.html")
    csvp = os.path.join(p["output_dir"], "岗位投递清单.csv")
    R.render(short, html, csvp, " · ".join(bits))
    print("[report] %s / %s" % (html, csvp))
    return html


def cmd_deliver(cfg, args):
    p = _ensure_dirs(cfg)
    short = json.load(open(os.path.join(p["data_dir"], "shortlist.json"), encoding="utf-8"))
    d = cfg["deliver"]
    tiers = _tiers(cfg, args.tiers)
    targets, seen = [], set()
    for t in tiers:
        for u in short.get(t, []):
            for j in u["top_jobs"][: (args.per_unit or d["per_unit"])]:
                if j["_url"] in seen:
                    continue
                seen.add(j["_url"])
                targets.append({"url": j["_url"], "pid": j["_url"].rsplit("/", 1)[-1],
                                "title": j["title"], "company": u["company"], "tier": t})
    targets = targets[: (args.limit or d["limit"])]
    print("[deliver] 待投递 %d 个岗位" % len(targets), flush=True)

    log = os.path.join(p["data_dir"], "deliver_log.csv")
    if not os.path.exists(log):
        with open(log, "w", encoding="utf-8-sig", newline="") as f:
            csv.writer(f).writerow(["时间", "梯队", "岗位", "单位", "结果", "链接"])

    ok = skip = fail = 0
    with B.Session(cfg["browser"]["port"], p["profile"], L.HOST) as s:
        for i, t in enumerate(targets, 1):
            if L.is_delivered(s.page, t["pid"]):
                res = "已投递过"
                skip += 1
            else:
                good, note = L.deliver(s.page, t["pid"])
                res = note
                if good:
                    ok += 1
                else:
                    fail += 1
            print("[%d/%d] %s %s | %s" % (i, len(targets), "OK" if res == "投递成功" else ("-" if res == "已投递过" else "!!"),
                                           t["company"][:18], t["title"][:16]), flush=True)
            with open(log, "a", encoding="utf-8-sig", newline="") as f:
                csv.writer(f).writerow([time.strftime("%Y-%m-%d %H:%M"), t["tier"],
                                        t["title"], t["company"], res, t["url"]])
            if res != "已投递过":
                time.sleep(random.randint(args.min_delay or d["min_delay"], args.max_delay or d["max_delay"]))
            else:
                time.sleep(2)
    print("[deliver] 成功 %d / 跳过 %d / 失败 %d" % (ok, skip, fail))
    return log


def cmd_cleanup(cfg, args):
    keep_hosts = {L.HOST}
    with B.Session(cfg["browser"]["port"], _paths(cfg)["profile"]) as s:
        pages = list(s.ctx.pages)
        keep, closed = {}, 0
        for pg in pages:
            url = pg.url or ""
            host = next((h for h in keep_hosts if h in url), None)
            if host is None:
                try:
                    pg.close()
                    closed += 1
                except Exception:
                    pass
            elif host in keep:
                try:
                    pg.close()
                    closed += 1
                except Exception:
                    pass
            else:
                keep[host] = pg
        print("[cleanup] 关闭 %d 个标签，保留 %d 个" % (closed, len(keep)))
    return closed


def main(argv=None):
    ap = argparse.ArgumentParser(prog="job-autopilot", description="岗位搜索与批量投递自动化")
    ap.add_argument("-c", "--config", default="config.json")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("collect").set_defaults(fn=cmd_collect)
    sub.add_parser("analyze").set_defaults(fn=cmd_analyze)
    sub.add_parser("report").set_defaults(fn=cmd_report)
    sub.add_parser("cleanup").set_defaults(fn=cmd_cleanup)
    sub.add_parser("run-all").set_defaults(fn=lambda cfg, a: _run_all(cfg, a))

    dv = sub.add_parser("deliver")
    dv.add_argument("--tiers", default=None)
    dv.add_argument("--per-unit", type=int, default=None)
    dv.add_argument("--limit", type=int, default=None)
    dv.add_argument("--min-delay", type=int, default=None)
    dv.add_argument("--max-delay", type=int, default=None)
    dv.set_defaults(fn=cmd_deliver)

    a = ap.parse_args(argv)
    cfg = C.load(a.config)
    a.fn(cfg, a)


def _run_all(cfg, args):
    cmd_collect(cfg, args)
    cmd_analyze(cfg, args)
    cmd_report(cfg, args)
    cmd_deliver(cfg, args)
    cmd_cleanup(cfg, args)


if __name__ == "__main__":
    main()
