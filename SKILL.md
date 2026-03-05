---
name: 13f-tracker
description: Fetches SEC 13F institutional holdings and outputs a fixed-format categorized narrative report (China Book / AI-Semi-US SaaS / Other US Book), with deterministic filtering/merging/formatting.
---

# 13F Holdings Analyzer Skill v2

⚠️ **CRITICAL: 必须通过 `run.sh` 调用，不要自己写 Python 抓取。**
⚠️ **CRITICAL: 固定格式输出由代码生成，agent 不要改写模板措辞。**

## 0) Setup
```bash
export EDGAR_IDENTITY="Your Name <your.email@example.com>"
```
首次运行会自动创建 `venv` 并安装依赖。

---

## 1) Health Check (mandatory)
```bash
bash skills/13f-tracker/run.sh --json self-test --institution 0001067983
```

---

## 2) Core Usage

### A) 固定格式报告（推荐）
```bash
bash skills/13f-tracker/run.sh --json compare --institution 0001762304 --offset 0 --format cn
```
或按季度直接指定（不用手算 offset）：
```bash
bash skills/13f-tracker/run.sh --json compare --institution 0001762304 --quarter 25Q4 --format cn
```

### B) 原始数据模式
```bash
bash skills/13f-tracker/run.sh --json compare --institution 0001762304 --offset 0 --format raw
```

### C) 其他命令
```bash
bash skills/13f-tracker/run.sh --json summary --institution 0001762304 --offset 0
bash skills/13f-tracker/run.sh --json top --institution 0001762304 --offset 0 --limit 10
bash skills/13f-tracker/run.sh --json search --query "hhlr"
```

---

## 3) What is now deterministic (code-level, not prompt-level)

1. **Biotech exclusion (default ON)**
   - 自动过滤 Bio/Therapeutics/Pharma/Genomics/Oncology 等关键词与已知 biotech tickers
   - 若要关闭过滤：`--include-biotech`

2. **Share-class merge**
   - 自动合并 GOOG+GOOGL → Alphabet, BRK.A+BRK.B → Berkshire Hathaway 等（见 `merge_rules.json`）

3. **Category classification**
   - 自动归类到：`China Book` / `AI/Semi/US SaaS` / `Other US Book`
   - 映射表在 `scripts/classification.json`

4. **Value formatting**
   - `>=100M` → `X.X亿美元`
   - `<100M` → `XX00万美元`（四舍五入到百万级）

5. **Strict Chinese templates**
   - 建仓 / 清仓 / 大幅加仓 / 加仓 / 减仓 / 仓位不变
   - 不依赖模型自由发挥

6. **Sorting discipline**
   - 各组内按当前 Value 降序
   - 清仓放该组最后

---

## 4) JSON Output Contract

### compare --format cn
```json
{
  "ok": true,
  "institution": "0001762304",
  "offset": 0,
  "manager": "...",
  "base_period": "2025-12-31",
  "rows": [...],
  "raw_text": "...",
  "formatted_report": "**China Book**\n- ...",
  "categories": {
    "China Book": ["..."],
    "AI/Semi/US SaaS": ["..."],
    "Other US Book": ["..."]
  },
  "total_positions": 18,
  "filtered_biotech": 4
}
```

### Error
```json
{"ok": false, "error": "...", "hint": "..."}
```

---

## 5) Institution Mapping

- 支持 CIK / Ticker / 机构名（大小写不敏感）
- 常用映射在 `scripts/institution_map.json`
- 例：`hhlr`, `高瓴` → `0001762304`

---

## 6) Agent Output Rule (very important)

当用户要求固定格式报告时：
1. 运行 `compare --format cn --json`
2. 直接使用 `formatted_report` 字段作为最终正文（可加 1 行上下文，不改模板）
3. 不要重新计算百分比，不要改动措辞
4. 若 `ok=false`，原样返回 `error + hint`
