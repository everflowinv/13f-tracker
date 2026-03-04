---
name: 13f-tracker
description: Fetches SEC 13F institutional holdings and formats them into a specific categorized narrative report.
---
# 13F Holdings Analyzer Skill

## Setup & Installation

⚠️ **CRITICAL: Installation Location**
Do NOT install this skill in the global `node_modules` directory. You MUST clone/install it directly into your local OpenClaw workspace:
1. Navigate to your workspace: `cd ~/.openclaw/workspace/skills/`
2. Clone this repository: `git clone git@github.com:everflowinv/13f-tracker.git`

**Configuration:**
Set your SEC Edgar identity (Required by SEC API to avoid rate limits/bans):
`export EDGAR_IDENTITY="Your Name <your.email@example.com>"`

**That's it!** You do NOT need to manually install dependencies. The skill is fully auto-bootstrapping. The first time the Agent executes the `run.sh` command, it will automatically create an isolated virtual environment and install everything needed.

## When to use this skill
Use this skill when a user asks about the stock portfolio changes, quarter-over-quarter comparisons, or specific holdings of an institutional investor.

## How to use this skill
⚠️ **AGENT INSTRUCTION: DO NOT write or execute your own Python code to fetch data.** You MUST use `run.sh` only.

### 0) Health check first (mandatory)
```bash
bash skills/13f-tracker/run.sh self-test --institution 0001067983
bash skills/13f-tracker/run.sh --json self-test --institution 0001067983
```

### 1) Fetch data (raw text mode)
```bash
bash skills/13f-tracker/run.sh compare --institution 0001762304 --offset 0
```

### 2) Fetch data (JSON mode, preferred for deterministic parsing)
```bash
bash skills/13f-tracker/run.sh --json compare --institution 0001762304 --offset 0
```
Then process the output EXACTLY according to the analytical steps below.

### Argument Mapping Rules
- `--institution`: You MUST extract the institution's identifier. For non-public funds (like HHLR Advisors), proactively search for and use their CIK number. For public companies, use the Ticker.
- `--offset`: An integer representing how many quarters to go back from the MOST RECENTLY filed 13F report. 
  - The script fetches reports in reverse chronological order.
  - `0` = The latest available quarter (e.g., typically 25Q4 if we are in early 2026).
  - `1` = One quarter ago (e.g., 25Q3).
  - `2` = Two quarters ago (e.g., 25Q2), and so on.
  - *Calculation Rule:* Identify the "base quarter" the user wants to analyze. Calculate how many quarters ago that was compared to the latest available quarter, and use that integer as the `--offset`. (Note: The `compare` command automatically compares the base quarter with its immediate preceding quarter).

### ⚠️ CRITICAL ANALYTICAL INSTRUCTIONS ⚠️
Act as an elite, highly disciplined data analyst. You MUST process the raw tabular data EXACTLY according to these 5 steps. Do NOT hallucinate data, and do NOT skip steps.

**Step 1: STRICT Biotech Exclusion & Merge**
- **Hard Filter**: You MUST strictly REMOVE any company with names containing: "Bio", "Therapeutics", "Pharma", "Medicines", "Life Sciences", "Genomics", "Oncology", or known biotech tickers (e.g., LEGN, ONC, MAZE, ALGS, CTKB, SGMT, AVBP, IMAB, GOSS, CONTINEUM). DO NOT include them in the final output under any circumstances.
- **Merge**: If a company has multiple share classes (e.g., Alphabet GOOG and GOOGL), merge them into a single entity. Sum their Shares and Values before calculating.

**Step 2: Absolute Categorization Rules**
Classify the remaining companies strictly into these 3 categories:
1. **China Book**: Any company headquartered or primarily operating in China (e.g., BABA, PDD, FUTU, BEKE, YSG, YMM, NTES, BIDU, UXIN, MOGU, TUYA, API, VNET, BULL).
2. **AI/Semi/US SaaS**: Tech giants, Artificial Intelligence, Semiconductors, and US Software (e.g., Alphabet/GOOGL, TSM, Amazon, Meta, Microsoft, CWAN).
3. **Other US Book**: All other companies that do not fit the above two (e.g., MCO, GE, B, EQX, IBIT, CAIFY).

**Step 3: Value Parsing & Formatting (CRITICAL MATH)**
IGNORE the "($K)" in the table header. The numbers like `$795,980,117` are the **EXACT ACTUAL DOLLAR AMOUNTS** (e.g., 795 Million Dollars). Strip the `$` and `,`, convert the raw number to millions (M), and apply this exact formatting:
- If Value >= 100,000,000 (100M): Format as `X.X亿美元` (Keep 1 decimal place. e.g., $795,980,117 -> 8.0亿美元).
- If Value < 100,000,000 (100M): Round to the nearest whole million and format as `XX00万美元` (e.g., $46,422,673 -> 4600万美元; $2,284,900 -> 200万美元).

**Step 4: Strict Natural Language Templates**
Calculate change percentage: `(Chg / Prev Shares) * 100`, rounded to the nearest integer.
You are strictly FORBIDDEN from inventing new phrases (Do NOT use "大幅减仓"). Use EXACTLY these templates:
- New Position: `建仓[Company]，[Value]`
- Closed Position: `清仓[Company]（之前持仓[Prev Value]）`
- Increased > 50%: `大幅加仓[Company] [Chg%]%至[Value]`
- Increased <= 50%: `加仓[Company] [Chg%]%至[Value]`
- Decreased (Any %): `减仓[Company] [Chg%]%至[Value]`
- Unchanged: `[Company]仓位不变，[Value]` (Ensure the company name comes FIRST).
*(Use short names: "Amazon" not "AMAZON COM INC", "Alphabet" not "ALPHABET INC".)*

**Step 5: Sorting & Final Output formatting**
- Group exactly by: `China Book`, `AI/Semi/US SaaS`, `Other US Book`.
- Under each group, sort ACTIVE positions descending by their CURRENT Value.
- Place all CLOSED (清仓) positions at the very bottom of that group.
- OUTPUT ONLY THE FINAL TEXT REPORT. Do not output your thinking process, do not apologize, do not explain your math.

### Output Discipline (Mandatory, low-intelligence-safe)
- Never invent institution mapping, holdings, or percentages.
- If command returns error/hint, surface it directly and stop.
- Prefer `--json` output for downstream parsing whenever possible.
- In final narrative, only use values that appear in tool output.

### Execution Example
User: "对比一下HHLR Advisors 25Q4和25Q3的持仓"
Action: Run `bash skills/13f-tracker/run.sh compare --institution 0001762304 --offset 0` (Assuming 25Q4 is the latest available quarter, making the base offset 0).