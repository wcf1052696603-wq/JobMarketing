# -*- coding: utf-8 -*-
"""岗位匹配：过滤、打分、按单位聚合。全部规则来自配置。"""
from collections import defaultdict


def classify_job_type(title, desc, rules, keep_keywords):
    text = (title or "") + " " + (desc or "")
    for rule in rules:
        for kw in rule.get("keywords", []):
            if kw in text:
                return rule["name"]
    return ""


def unit_kind(name, rules):
    for rule in rules:
        for kw in rule.get("keywords", []):
            if kw in name:
                return rule["name"]
    return "其他"


def hit_any(text, words):
    return any(w in text for w in words or [])


def filter_items(items, f):
    core = set(f.get("core_disciplines") or [])
    near = set(f.get("near_disciplines") or [])
    req = f.get("require_any_discipline") or []
    inc = set(f.get("include_city_names") or [])
    exc = set(f.get("exclude_city_names") or [])
    exc_co = f.get("exclude_company_keywords") or []
    exc_t = f.get("exclude_title_keywords") or []

    kept = []
    for it in items:
        city = (it.get("city") or "").strip()
        company = it.get("company") or ""
        title = it.get("title") or ""
        if inc and city not in inc:
            continue
        if city in exc:
            continue
        if hit_any(company, exc_co):
            continue
        if hit_any(title, exc_t):
            continue
        tags = set(it.get("tags") or [])
        subj = it.get("subject") or ""
        blob = title + " " + subj + " " + " ".join(tags) + " " + (it.get("desc") or "")
        if req and not (hit_any(blob, req)):
            continue
        if not (tags & (core | near) or hit_any(subj, req)):
            continue
        it["_kind"] = unit_kind(company, f.get("unit_kind_rules") or [])
        kept.append(it)
    return kept


def score(item, s, job_type):
    v = 0
    tags = set(item.get("tags") or [])
    title = item.get("title") or ""
    if tags & set(s.get("near_disciplines_effective", []) or []) or set(s.get("core_disciplines_effective", []) or []) & tags:
        pass
    return v


def score_item(it, s, job_type):
    v = 0
    tags = set(it.get("tags") or [])
    title = it.get("title") or ""
    if tags & set(s["_core"]):
        v += s.get("core_discipline", 5)
    if tags & set(s["_near"]):
        v += s.get("near_discipline", 3)
    for kw in s.get("tech_title_keywords") or []:
        if kw in title:
            v += s.get("tech_title_bonus", 2)
            break
    if job_type:
        v += s.get("known_job_type", 2)
    if it.get("salary_str") and it["salary_str"] != "面议":
        v += s.get("salary_disclosed", 1)
    if it.get("_kind") in (s.get("preferred_kinds") or []):
        v += s.get("preferred_kind_bonus", 2)
    if hit_any(it.get("company") or "", s.get("penalized_company_keywords") or []):
        v -= s.get("penalized_company_penalty", 2)
    return v


def aggregate(items, s, cfg_filters, type_rules, keep_keywords):
    groups = defaultdict(list)
    for it in items:
        jt = classify_job_type(it.get("title"), it.get("desc"), type_rules, keep_keywords)
        if not jt:
            if not hit_any(it.get("title") or "", keep_keywords):
                continue
            jt = "其他教职/科研岗"
        it["_type"] = jt
        it["_score"] = score_item(it, s, jt)
        groups[(it["company_id"], it["company"])].append(it)

    units = []
    for (cid, cname), jobs in groups.items():
        jobs.sort(key=lambda x: -x["_score"])
        best = jobs[0]
        units.append({
            "company_id": cid,
            "company": cname,
            "city": best["city"],
            "kind": best["_kind"],
            "unit_url": s["_unit_url"](cid),
            "job_count": len(jobs),
            "max_score": max(j["_score"] for j in jobs),
            "types": sorted(set(j["_type"] for j in jobs)),
            "top_jobs": jobs[:4],
            "salary": next((j["salary_str"] for j in jobs if j["salary_str"] != "面议"), "面议"),
        })
    units.sort(key=lambda u: (-u["max_score"], -u["job_count"]))
    return units


def split_tiers(units, s):
    t1, t2, t3 = [], [], []
    for u in units:
        if u["max_score"] >= s.get("tier1_min", 12):
            t1.append(u)
        elif u["max_score"] >= s.get("tier2_min", 9):
            t2.append(u)
        else:
            t3.append(u)
    return t1, t2, t3
