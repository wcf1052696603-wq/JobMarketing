# job-autopilot

招聘平台的**岗位搜索 → 匹配打分 → 批量投递**自动化工具。

最初是为"高校教职 / 博士人才引进"场景写的，但**专业、学历、地区、岗位类型全部由配置文件决定**，改成任何求职目标都能直接用——把 `config.json` 里的关键词和城市换掉即可，代码里没有任何硬编码的"力学""博士""广东"。

当前支持平台：**理聘**（lipind.com，硕博学术科研人才招聘平台）。

---

## 它能做什么

| 环节 | 说明 |
| --- | --- |
| collect | 按关键词批量拉取岗位，去重后落地 |
| analyze | 按学科 / 地区 / 岗位类型过滤并打分，按招聘单位聚合分梯队 |
| report | 生成可勾选、可筛选、可导出 CSV 的 HTML 清单 |
| deliver | 逐个投递，带随机节流，已投过的自动跳过，结果写入日志 |
| cleanup | 关闭多余浏览器标签页 |
| run-all | 以上全流程串起来跑 |

投递动作走的是平台页面上的真实按钮（平台没有可直接调用的投递接口），并且会**在投递后复查平台返回的投递状态**，所以投递结果是可验证的，不是"点了就算"。

---

## 安装

```bash
pip install playwright
```

浏览器用你本机已装的 **Edge 或 Chrome**（不是 Playwright 自带的无头浏览器），这样登录态保存在独立 profile 里，反自动化检测也更难过。

## 使用

### 1. 准备配置

```bash
cp config.example.json config.json
```

编辑 `config.json`，至少改这几个字段：

```json
{
  "search": {
    "keywords": ["你的方向", "相关方向"],
    "edu_level_name": "博士",
    "company_type_name": "高等教育单位"
  },
  "filters": {
    "include_city_names": [],
    "exclude_city_names": [],
    "core_disciplines": ["你的核心方向"],
    "near_disciplines": ["相关方向"],
    "exclude_title_keywords": ["实习"]
  }
}
```

`config.py` 里内置了全国各省份 → 城市的映射，配置时可以直接写地区名，`expand_regions(["广东","江浙沪"])` 会展开成城市列表。

### 2. 登录（只需一次）

```bash
python -m jobautopilot collect
```

首次运行时会弹出一个浏览器窗口。**在这个窗口里手动完成登录**（扫码 / 短信 / 滑块都自己过），登录态会保存在 `paths.browser_profile` 目录里，之后不用再登录。

> 为什么要手动登录：平台有短信验证码和滑块验证，自动化过不去。工具只接管登录之后的搜索和投递。

### 3. 跑

```bash
python -m jobautopilot run-all                    # 全流程
python -m jobautopilot collect                    # 只抓岗位
python -m jobautopilot analyze && python -m jobautopilot report
python -m jobautopilot deliver --tiers tier1 --per-unit 1 --limit 40
python -m jobautopilot cleanup                    # 收尾清标签页
```

产物：`outputs/岗位投递清单.html`、`outputs/岗位投递清单.csv`、`data/deliver_log.csv`。

---

## 配置项说明

### search

| 字段 | 说明 |
| --- | --- |
| keywords | 搜索关键词，每个关键词单独分页抓取 |
| max_pages_per_keyword | 每个关键词最多翻几页 |
| page_size | 每页条数，上限 100 |
| edu_level_name | 学历，**按名称填**，运行时自动查字典转 id；留空不限 |
| company_type_name | 单位类型，同上；留空不限 |

### filters

| 字段 | 说明 |
| --- | --- |
| include_city_names | 只保留这些城市；留空不限 |
| exclude_city_names | 排除这些城市 |
| exclude_company_keywords | 单位名含这些词的直接排除 |
| exclude_title_keywords | 岗位标题含这些词的直接排除 |
| core_disciplines | 学科标签命中这些算核心对口 |
| near_disciplines | 命中这些算相近方向 |
| require_any_discipline | 学科标签或专业字段必须命中其一，否则丢弃 |
| unit_kind_rules | 单位类型归类规则（按名称关键字） |

### scoring

打分权重，决定梯队划分。默认 `tier1_min=12`、`tier2_min=9`：

- 核心学科 `+5`，相近学科 `+3`
- 标题命中技术关键词（如"有限元""仿真"）`+2`
- 岗位类型能归到已定义类型 `+2`
- 薪资写明了具体数字 `+1`
- 单位类型在 preferred_kinds 里 `+2`
- 单位名命中 penalized_company_keywords `-2`

### deliver

| 字段 | 说明 |
| --- | --- |
| tiers | 投递哪些梯队 |
| per_unit | 同一家单位最多投几个岗位 |
| limit | 单次最多投多少个 |
| min_delay / max_delay | 两次投递之间的随机间隔（秒） |

---

## 两个容易踩的坑

**1. 「消息」页看不到投递记录 ≠ 没投成功**

平台的「消息」页显示的是沟通会话，只有在投递的同时平台代发了"打招呼"才会生成卡片，而平台对自动打招呼有频率限制。判断是否投递成功的权威依据是平台接口返回的 `is_deliver`，工具每次投递后都会复查这个字段。

**2. 投递节奏要克制**

`min_delay` 建议不低于 15 秒。短时间高频投递容易触发平台风控。单日投递量建议控制在 50 以内，宁可分摊到几天。

---

## 已知不支持的平台

**BOSS 直聘、猎聘** 会检测自动化：一旦浏览器被自动化连接，页面会在几秒内自动跳转成空白页（两种独立的自动化接入方式都验证过）。这两个平台只能用你自己的浏览器手动操作，本工具不做尝试。

---

## 免责声明

仅供个人求职使用。使用前请确认你的用法不违反目标平台的用户协议；工具内置了随机节流来降低对平台的压力，请勿移除节流逻辑或用于批量注册、爬取等无关用途。
