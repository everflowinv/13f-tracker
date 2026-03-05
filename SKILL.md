---
name: 13f-tracker
description: Fetches SEC 13F institutional holdings and outputs a fixed-format categorized narrative report (China Book / AI-Semi-US SaaS / Other US Book), with deterministic filtering/merging/formatting.
---

# 13F Holdings Analyzer Skill v3

⚠️ **CRITICAL: 必须通过 `run.sh` 调用，不要自己写 Python 抓取。**
⚠️ **CRITICAL: 固定格式输出由代码生成，agent 不要改写模板措辞。**
⚠️ **CRITICAL: 分类 JSON 只接受 SEC ticker（如 `DASH`），不接受公司名（如 `DOORDASH`）。系统会自动解析公司名→ticker，无需手动转换。**

## 0) Setup
```bash
export EDGAR_IDENTITY="Your Name <your.email@example.com>"
```
首次运行会自动创建 `venv` 并安装依赖。

---

## 1) Health Check (mandatory first run)
```bash
bash skills/13f-tracker/run.sh --json self-test --institution 0001067983
```

---

## 2) Core Usage

### A) 固定格式报告（推荐）
```bash
bash skills/13f-tracker/run.sh --json compare --institution HHLR --quarter 25Q4 --format cn
```
- `--quarter 25Q4` 等同于 `--offset 0`（如果 25Q4 是最新季度）
- 输出的 `formatted_report` 字段就是完整中文报告，**直接贴给用户，不做任何修改**

### B) 原始数据模式
```bash
bash skills/13f-tracker/run.sh --json compare --institution HHLR --quarter 25Q4 --format raw
```

### C) 其他命令
```bash
bash skills/13f-tracker/run.sh --json summary --institution HHLR --quarter 25Q4
bash skills/13f-tracker/run.sh --json top --institution HHLR --quarter 25Q4 --limit 10
bash skills/13f-tracker/run.sh --json search --query "aspex"
```

---

## 3) 输出模板说明（代码自动生成，不要改写）

### 基础模板
| 场景 | 输出格式 | 示例 |
|------|---------|------|
| 新建仓 | `建仓{name}，{金额}` | 建仓Nvidia，5.4亿美元 |
| 清仓 | `清仓{name}（之前持仓{金额}）` | 清仓Baidu（之前持仓4900万美元） |
| 大幅加仓（>50%） | `大幅加仓{name}至{金额}，之前持仓{金额}` | 大幅加仓Grab至3.0亿美元，之前持仓1.7亿美元 |
| 加仓（3-50%） | `加仓{name} {pct}%至{金额}` | 加仓FUTU 38%至5.5亿美元 |
| 减仓（>2%） | `减仓{name} {pct}%至{金额}` | 减仓Sea 21%至4.3亿美元 |
| 几乎不变（≤2%） | `{name}仓位几乎不变，{金额}` | PDD仓位几乎不变，3.5亿美元 |
| 完全不变（0%） | `{name}仓位不变，{金额}` | YMM仓位不变，2.5亿美元 |

### 连续趋势前缀（自动生成）
系统会自动拉取上一期对比数据。如果满足以下条件，输出前自动加趋势前缀：

| 当期动作 | 上期同公司动作 | 前缀 |
|---------|--------------|------|
| 加仓/大幅加仓 | 建仓 | `继{上期Q}建仓后，继续` |
| 加仓/大幅加仓 | 加仓/大幅加仓 | `继{上期Q}加仓后，继续` |
| 减仓 | 减仓 | `继{上期Q}减仓后，继续` |

示例：`继25Q3建仓后，继续加仓Amer Sports 28%至2.8亿美元`

### 可转债（CB）识别
- 通过 CUSIP 第 7-8 位自动识别：含字母 = 债券/CB，纯数字 = 正股
- CB 持仓名称自动追加 ` CB` 后缀（如 `H World CB`）
- CB 与正股独立计算，不合并

### 金额格式
- ≥1亿美元 → `X.X亿美元`
- <1亿美元 → `XX00万美元`（四舍五入到百万）

---

## 4) 分类体系

三个类别：`China Book` / `AI/Semi/US SaaS` / `Other US Book`

映射表在 `scripts/classification.json`，auto-learn 自动维护。

### ⚠️ 分类写入规则（重要）
- **只接受 SEC ticker 格式**（1-6 个大写字母）
- 如果用户给的是公司名（如 "Doordash"），系统会**自动解析**为对应 ticker（如 "DASH"）
- 解析依赖 `scripts/name_to_ticker.json`（每次 compare 时从 SEC 数据自动更新）
- 如果公司名无法解析，系统会拒绝写入并提示先运行 compare
- **不要**手动编辑 classification.json 写入公司全名

### ⚠️ Ticker Alias 机制（重要）
某些公司的 SEC filing ticker 与常用 ticker 不同（如 TAL Education 在 SEC 中为 `XRS`，但用户习惯用 `TAL`）。

**`scripts/ticker_aliases.json`** 解决此问题：
```json
{
  "XRS": "TAL",
  "FB": "META"
}
```
- **键** = SEC filing 中使用的 ticker
- **值** = classification.json 中用户设定的 ticker
- 分类时先查 alias → 用解析后的 ticker 查分类
- **Auto-learn**：compare 时如果 SEC ticker 未分类，但 issuer name 能通过 `name_to_ticker.json` 关联到已分类 ticker，自动写入 alias
- 手动维护：`map-propose --instruction "alias XRS -> TAL"`

---

## 5) 维护映射表

### 自然语言维护（推荐）
先生成 patch 预览：
```bash
bash skills/13f-tracker/run.sh --json map-propose --instruction "把 DASH 从 AI 改到 Other"
```
确认后应用：
```bash
bash skills/13f-tracker/run.sh --json map-apply --patch-id p1741140000
```

支持的指令样式（ticker 或公司名均可，系统自动解析）：
- `把 Doordash 从 AI 改到 Other` → 自动识别为 DASH
- `NVDA 分类到 AI`
- `Coupang 归类到 Other` → 自动识别为 CPNG
- `hhlr -> 0001762304`（机构别名）
- `merge GOOG,GOOGL -> Alphabet`（合并 share class）
- `alias XRS -> TAL`（SEC ticker 别名）
- `XRS 实际是 TAL`（中文写法）

### 查看映射
```bash
bash skills/13f-tracker/run.sh --json map-show --type all
bash skills/13f-tracker/run.sh --json map-show --type alias
bash skills/13f-tracker/run.sh --json map-show --type classification --key DASH
```

---

## 6) Auto-Learn

默认开启（`--auto-learn true`），每次 compare 后自动：
- 新 ticker → fallback 分类写入 `classification.json`
- 新机构别名 → 写入 `institution_map.json`
- Share class 关系 → 写入 `merge_rules.json`
- 公司名→ticker 映射 → 写入 `name_to_ticker.json`
- **SEC ticker 别名** → 写入 `ticker_aliases.json`（当 SEC ticker 与已分类 ticker 不一致时）
- 审计日志 → `temp/auto_learn_log.jsonl`

关闭：`--auto-learn false`

---

## 7) Institution 查找

支持 CIK / Ticker / 机构名（大小写不敏感）：
```bash
--institution 0001762304    # CIK
--institution HHLR          # 机构别名
--institution "Aspex"       # 机构名
```
映射在 `scripts/institution_map.json`。未找到时用 `search` 命令查：
```bash
bash skills/13f-tracker/run.sh --json search --query "aspex"
```

---

## 8) JSON Output Contract

### compare --format cn
```json
{
  "ok": true,
  "institution": "...",
  "offset": 0,
  "manager": "Aspex Management (HK) Ltd",
  "base_period": "2025-12-31",
  "rows": [...],
  "formatted_report": "**China Book**\n- 加仓FUTU 38%至5.5亿美元\n...",
  "categories": {
    "China Book": ["..."],
    "AI/Semi/US SaaS": ["..."],
    "Other US Book": ["..."]
  },
  "total_positions": 25,
  "filtered_biotech": 4
}
```

### Error
```json
{"ok": false, "error": "...", "hint": "..."}
```

---

## 9) Biotech 过滤

默认开启，自动排除 Bio/Therapeutics/Pharma/Genomics 等。
关闭：`--include-biotech`

---

## 10) Agent Output Rule（⚠️ 必须遵守）

当用户要求固定格式报告时：
1. 运行 `compare --format cn --json`
2. **直接使用 `formatted_report` 字段**作为最终回复
3. 可在报告前加 1 行上下文（如机构名和季度），**不要修改报告内容**
4. **不要**重新计算百分比、改动措辞、重排顺序、重新分类
5. **不要**根据自己的判断把公司从一个类别移到另一个——分类完全由代码决定
6. 若 `ok=false`，返回 `error + hint`

### 示例回复格式
```
Aspex Management 25Q4 vs 25Q3：

**China Book**
- 加仓FUTU 38%至5.5亿美元
- PDD仓位几乎不变，3.5亿美元
...
```

### ❌ 禁止的行为
- ❌ 把 `formatted_report` 中 China Book 下的公司移到 AI/Semi（代码已正确分类）
- ❌ 修改金额数字（如把"4.5亿"改成"4.50亿"）
- ❌ 重新排序（代码按持仓市值降序排列）
- ❌ 添加自己的分析评论到报告条目中
- ❌ 省略任何条目

---

## 11) 数据文件清单

| 文件 | 用途 | 维护方式 |
|------|------|---------|
| `scripts/classification.json` | ticker → 三大类别 | auto-learn + map-propose |
| `scripts/institution_map.json` | 机构别名 → CIK | auto-learn + map-propose |
| `scripts/merge_rules.json` | share class 合并 | auto-learn + map-propose |
| `scripts/name_to_ticker.json` | 公司名 → SEC ticker | auto-learn (compare 时) |
| `scripts/ticker_aliases.json` | SEC ticker → 分类用 ticker | auto-learn + map-propose |
| `temp/auto_learn_log.jsonl` | 所有 auto-learn 审计日志 | 自动追加 |
