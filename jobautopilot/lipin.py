# -*- coding: utf-8 -*-
"""理聘（lipind.com）接口与页面操作封装。

接口是通过观察站内请求得到的，不是公开 API，随时可能变动；
投递动作走的是页面按钮（平台没有可直接调用的投递接口）。
"""
import json
import random
import time

HOST = "lipind.com"
BASE = "https://www.lipind.com"

FETCH_JS = "async (u) => { const r = await fetch(u, {credentials:'include'}); return await r.text(); }"
CLICK_JS = """(t) => {
  const ns = [...document.querySelectorAll('button,a,div,span')]
    .filter(e => e.children.length === 0 && e.textContent.trim() === t && e.offsetParent !== null);
  if (!ns.length) return 0;
  ns[0].click();
  return 1;
}"""


def get(page, path):
    raw = page.evaluate(FETCH_JS, path)
    try:
        return json.loads(raw)
    except Exception:
        return {"state": -1, "raw": raw[:200]}


def load_dict(page):
    """岗位筛选字典：城市、学历、单位类型、学科。"""
    d = get(page, "/api/basic/position-params").get("data") or {}
    out = {"edu": {}, "company_type": {}, "city": {}, "subjects": []}
    for it in d.get("edu_level") or []:
        out["edu"][it["name"]] = it["id"]
    for it in d.get("cp_type") or []:
        out["company_type"][it["name"]] = it["id"]
    for grp in d.get("city") or []:
        for c in grp.get("children") or []:
            out["city"][c["name"]] = c["id"]
    return out


def search(page, keyword, edu_id=None, cp_id=None, page_no=1, size=100):
    url = "/api/v2/basic/positions?page=%d&size=%d" % (page_no, size)
    if edu_id:
        url += "&edu_level=%s" % edu_id
    if cp_id:
        url += "&cp_type=%s" % cp_id
    if keyword:
        url += "&keyword=%s" % keyword
    d = get(page, url)
    return (d.get("data") or []), d.get("total")


def relation(page, pid):
    d = get(page, "/api/basic/position-user-relation?id_=%s" % pid)
    return (d.get("data") or {})


def is_delivered(page, pid):
    return bool(relation(page, pid).get("is_deliver"))


def position_url(pid):
    return "%s/position/detail/%s.html" % (BASE, pid)


def unit_url(cid):
    return "%s/unit/detail/%s" % (BASE, cid)


def deliver(page, pid, deliver_text="投简历", confirm_text="确定"):
    """在职位详情页完成一次投递，返回 (是否投递, 备注)。"""
    page.bring_to_front()
    page.goto(position_url(pid), wait_until="domcontentloaded", timeout=60000)
    page.bring_to_front()
    page.wait_for_timeout(random.randint(2500, 4000))
    if not page.evaluate(CLICK_JS, deliver_text):
        return False, "无投递按钮"
    page.wait_for_timeout(2200)
    page.evaluate(CLICK_JS, confirm_text)
    page.wait_for_timeout(3200)
    ok = is_delivered(page, pid)
    return ok, ("投递成功" if ok else "疑似失败")
