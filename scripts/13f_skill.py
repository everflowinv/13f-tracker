#!/usr/bin/env python3
"""13F Holdings Analyzer v2 — deterministic formatting, auto-classification, biotech filter."""
import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

import pandas as pd
from edgar import Company, set_identity

pd.set_option("display.max_rows", None)
pd.set_option("display.max_columns", None)
pd.set_option("display.width", 2000)
pd.set_option("display.max_colwidth", None)

SCRIPT_DIR = Path(__file__).resolve().parent

# ---------------------------------------------------------------------------
# Identity
# ---------------------------------------------------------------------------
if "EDGAR_IDENTITY" in os.environ:
    set_identity(os.environ["EDGAR_IDENTITY"])
else:
    print("WARNING: EDGAR_IDENTITY not set.", file=sys.stderr)
    set_identity("OpenClaw_Agent <bot@openclaw.ai>")

# ---------------------------------------------------------------------------
# Data files
# ---------------------------------------------------------------------------
def _load_json(name: str) -> dict:
    p = SCRIPT_DIR / name
    if p.exists():
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


_CLASSIFICATION = _load_json("classification.json")
_MERGE_RULES = _load_json("merge_rules.json")
_INSTITUTION_MAP = _load_json("institution_map.json")

_CHINA_TICKERS = set(_CLASSIFICATION.get("china_book", []))
_AI_SEMI_TICKERS = set(_CLASSIFICATION.get("ai_semi_saas", []))

_BIOTECH_KEYWORDS = [
    "bio", "therapeutics", "pharma", "medicines", "life sciences",
    "genomics", "oncology", "immun", "geneg", "biopharma",
]
_BIOTECH_TICKERS = {
    "LEGN", "ONC", "MAZE", "ALGS", "CTKB", "SGMT", "AVBP", "IMAB",
    "GOSS", "CONTINEUM", "ZLAB", "BGNE", "MRNA", "BNTX",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _emit(payload: dict, as_json: bool = False):
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, default=str))
    else:
        print(json.dumps(payload, ensure_ascii=False, default=str, indent=2))


def _error_hint(msg: str) -> str:
    m = (msg or "").lower()
    if "edgar_identity" in m or "user-agent" in m:
        return "Set EDGAR_IDENTITY: export EDGAR_IDENTITY='Name <email>'"
    if "not enough" in m:
        return "Reduce --offset or verify the institution has enough 13F history."
    if "ssl" in m or "tls" in m or "eof" in m:
        return "Network/TLS issue. Check proxy and access to data.sec.gov."
    if "finding institution" in m or "not found" in m:
        return "Use a valid ticker, CIK, or institution name from institution_map.json."
    if "rate" in m or "429" in m:
        return "SEC rate limit. Wait 10s and retry."
    return "Check parameters and network; then retry."


def _retry(fn, max_retries=2, delay=2.0):
    last_err = None
    for attempt in range(max_retries + 1):
        try:
            return fn()
        except Exception as e:
            last_err = e
            err_str = str(e).lower()
            is_transient = any(k in err_str for k in [
                "timeout", "timed out", "connection", "reset", "429",
                "rate", "ssl", "eof", "too many",
            ])
            if not is_transient or attempt >= max_retries:
                raise
            time.sleep(delay * (attempt + 1))
    raise last_err


# ---------------------------------------------------------------------------
# Institution resolution (#7)
# ---------------------------------------------------------------------------
def _resolve_institution(identifier: str):
    """Resolve institution from name/CIK/ticker."""
    # Check institution map (case-insensitive)
    mapped = _INSTITUTION_MAP.get(identifier.lower().strip())
    if mapped:
        identifier = mapped

    # Strip comment key
    if identifier.startswith("_"):
        raise RuntimeError(f"Invalid institution: {identifier}")

    try:
        if identifier.isdigit() or (identifier.startswith("0") and identifier.replace("0", "").isdigit()):
            return Company(int(identifier))
        return Company(identifier)
    except Exception as e:
        raise RuntimeError(f"Error finding institution '{identifier}': {e}") from e


# ---------------------------------------------------------------------------
# Quarter parsing (#6)
# ---------------------------------------------------------------------------
def _quarter_to_offset(quarter_str: str, company) -> int:
    """Convert '25Q4' or '2025Q4' to offset from latest filing."""
    m = re.match(r"(\d{2,4})[Qq](\d)", quarter_str)
    if not m:
        raise ValueError(f"Invalid quarter format: '{quarter_str}'. Use e.g. '25Q4' or '2025Q3'.")

    year = int(m.group(1))
    if year < 100:
        year += 2000
    q = int(m.group(2))

    # Quarter end months: Q1=Mar, Q2=Jun, Q3=Sep, Q4=Dec
    q_end_month = {1: 3, 2: 6, 3: 9, 4: 12}
    if q not in q_end_month:
        raise ValueError(f"Invalid quarter number: Q{q}")

    target_period = f"{year}-{q_end_month[q]:02d}"

    # Scan filings to find offset
    filings = _retry(lambda: company.get_filings(form="13F-HR"))
    for i in range(min(len(filings), 20)):
        try:
            obj = filings[i].obj()
            period = str(obj.report_period)
            if period.startswith(target_period):
                return i
        except Exception:
            continue

    raise RuntimeError(f"Could not find 13F filing for {quarter_str} (target period: {target_period}-*)")


# ---------------------------------------------------------------------------
# Biotech filter (#2)
# ---------------------------------------------------------------------------
def _is_biotech(ticker: str, issuer: str) -> bool:
    if ticker and ticker.upper() in _BIOTECH_TICKERS:
        return True
    issuer_lower = (issuer or "").lower()
    return any(kw in issuer_lower for kw in _BIOTECH_KEYWORDS)


# ---------------------------------------------------------------------------
# Classification (#3)
# ---------------------------------------------------------------------------
def _classify(ticker: str) -> str:
    t = (ticker or "").upper()
    # Check merge rules first
    canonical = _MERGE_RULES.get(t, _MERGE_RULES.get(ticker, ""))
    if canonical:
        # Re-check with any ticker that maps to this canonical
        for k, v in _MERGE_RULES.items():
            if v == canonical and k.upper() in _CHINA_TICKERS:
                return "China Book"
            if v == canonical and k.upper() in _AI_SEMI_TICKERS:
                return "AI/Semi/US SaaS"

    if t in _CHINA_TICKERS:
        return "China Book"
    if t in _AI_SEMI_TICKERS:
        return "AI/Semi/US SaaS"
    return "Other US Book"


# ---------------------------------------------------------------------------
# Short name (#4 Step 4)
# ---------------------------------------------------------------------------
_SHORT_NAMES = {
    "AMAZON COM INC": "Amazon", "ALPHABET INC": "Alphabet",
    "META PLATFORMS INC": "Meta", "MICROSOFT CORP": "Microsoft",
    "APPLE INC": "Apple", "NVIDIA CORP": "NVIDIA",
    "TAIWAN SEMICONDUCTOR MFG CO LTD": "TSM",
    "BROADCOM INC": "Broadcom", "TESLA INC": "Tesla",
    "ALIBABA GROUP HOLDING LTD": "Alibaba",
    "PINDUODUO INC": "PDD", "PDD HOLDINGS INC": "PDD",
    "JD COM INC": "JD", "JD.COM INC": "JD",
    "BAIDU INC": "Baidu", "NETEASE INC": "NetEase",
    "FUTU HOLDINGS LTD": "FUTU", "KE HOLDINGS INC": "BEKE",
    "FULL TRUCK ALLIANCE CO LTD": "YMM",
    "ISHARES BITCOIN TRUST ETF": "IBIT",
}


def _short_name(issuer: str, ticker: str) -> str:
    """Get short display name."""
    # Check canonical merge name
    canonical = _MERGE_RULES.get((ticker or "").upper())
    if canonical and not canonical.startswith("_"):
        return canonical

    # Check short name map
    issuer_upper = (issuer or "").upper().strip()
    if issuer_upper in _SHORT_NAMES:
        return _SHORT_NAMES[issuer_upper]

    # Fallback: title-case first two words
    parts = (issuer or "").split()
    if len(parts) >= 2:
        name = " ".join(parts[:2]).title()
        # Remove trailing "Inc", "Corp", "Ltd"
        name = re.sub(r"\s+(Inc|Corp|Ltd|Plc|Co|Llc)\.?$", "", name, flags=re.IGNORECASE)
        return name
    return issuer or ticker or "Unknown"


# ---------------------------------------------------------------------------
# Value formatting (#1 Step 3)
# ---------------------------------------------------------------------------
def _format_value(value: float) -> str:
    """Format value in Chinese convention. Value is in actual USD."""
    if value >= 100_000_000:
        yi = value / 100_000_000
        return f"{yi:.1f}亿美元"
    else:
        wan = round(value / 10_000)
        # Round to nearest hundred wan
        wan = round(wan / 100) * 100
        # Avoid 0 for non-zero positions
        if value > 0 and wan == 0:
            wan = 100
        return f"{wan}万美元"


# ---------------------------------------------------------------------------
# Change template (#1 Step 4)
# ---------------------------------------------------------------------------
def _change_template(name: str, value: float, prev_shares: int, chg_shares: int,
                     prev_value: float) -> str:
    val_str = _format_value(value)

    if prev_shares == 0 and chg_shares > 0:
        return f"建仓{name}，{val_str}"

    if chg_shares == 0 and prev_shares > 0:
        # Could be unchanged or reduced to zero via value
        return f"{name}仓位不变，{val_str}"

    if prev_shares > 0 and (prev_shares + chg_shares) == 0:
        prev_val_str = _format_value(prev_value)
        return f"清仓{name}（之前持仓{prev_val_str}）"

    if prev_shares > 0:
        pct = round(abs(chg_shares) / prev_shares * 100)
        if chg_shares > 0:
            if pct > 50:
                return f"大幅加仓{name} {pct}%至{val_str}"
            else:
                return f"加仓{name} {pct}%至{val_str}"
        else:
            return f"减仓{name} {pct}%至{val_str}"

    return f"{name}仓位不变，{val_str}"


# ---------------------------------------------------------------------------
# Core: build formatted report (#1)
# ---------------------------------------------------------------------------
def _build_report(comparison_rows: list, exclude_biotech: bool = True) -> dict:
    """Process comparison rows into categorized, formatted report."""

    # Step 1: Filter biotech + merge share classes
    merged = {}
    for row in comparison_rows:
        ticker = str(row.get("Ticker") or row.get("ticker") or "").upper().strip()
        issuer = str(row.get("Issuer") or row.get("issuer") or "")

        if exclude_biotech and _is_biotech(ticker, issuer):
            continue

        # Determine merge key
        canonical = _MERGE_RULES.get(ticker)
        merge_key = canonical or _short_name(issuer, ticker)

        if merge_key not in merged:
            merged[merge_key] = {
                "name": merge_key,
                "ticker": ticker,
                "issuer": issuer,
                "shares": 0, "value": 0,
                "prev_shares": 0, "prev_value": 0,
                "chg_shares": 0,
                "category": _classify(ticker),
            }

        entry = merged[merge_key]
        # Accumulate
        shares = _safe_int(row.get("SharesPrnAmount") or row.get("Shares") or row.get("shares") or 0)
        value = _safe_float(row.get("Value") or row.get("value") or 0)
        chg = _safe_int(row.get("ShareChange") or row.get("Chg") or row.get("chg") or row.get("Change") or 0)

        entry["shares"] += shares
        entry["value"] += value
        entry["chg_shares"] += chg

        # Calculate prev shares (prefer explicit PrevShares)
        prev_shares_explicit = _safe_int(row.get("PrevShares") or row.get("Prev Shares") or row.get("prev_shares") or 0)
        if prev_shares_explicit > 0:
            entry["prev_shares"] += prev_shares_explicit
        elif shares > 0 or chg != 0:
            entry["prev_shares"] += max(0, shares - chg)

        # Try to get prev value
        prev_val = _safe_float(row.get("PrevValue") or row.get("Prev Value") or row.get("prev_value") or 0)
        if prev_val > 0:
            entry["prev_value"] += prev_val
        elif entry["prev_shares"] > 0 and entry["shares"] > 0:
            # Estimate prev value proportionally
            ratio = entry["prev_shares"] / max(entry["shares"], 1)
            entry["prev_value"] = entry["value"] * ratio

    # Step 2-5: Categorize, format, sort
    categories = {"China Book": [], "AI/Semi/US SaaS": [], "Other US Book": []}

    for entry in merged.values():
        cat = entry["category"]
        if cat not in categories:
            cat = "Other US Book"

        is_closed = entry["shares"] == 0 and entry["prev_shares"] > 0
        text = _change_template(
            entry["name"], entry["value"],
            entry["prev_shares"], entry["chg_shares"],
            entry["prev_value"]
        )

        categories[cat].append({
            "text": text,
            "value": entry["value"],
            "is_closed": is_closed,
            "name": entry["name"],
            "ticker": entry["ticker"],
            "shares": entry["shares"],
            "prev_shares": entry["prev_shares"],
            "chg_shares": entry["chg_shares"],
        })

    # Sort: active positions by value desc, closed at bottom
    report_lines = []
    for cat_name in ["China Book", "AI/Semi/US SaaS", "Other US Book"]:
        items = categories[cat_name]
        if not items:
            continue
        active = sorted([i for i in items if not i["is_closed"]], key=lambda x: -x["value"])
        closed = [i for i in items if i["is_closed"]]
        report_lines.append(f"\n**{cat_name}**")
        for item in active + closed:
            report_lines.append(f"- {item['text']}")

    return {
        "report_text": "\n".join(report_lines),
        "categories": {k: [i["text"] for i in v] for k, v in categories.items() if v},
        "total_positions": sum(len(v) for v in categories.values()),
        "filtered_biotech": len(comparison_rows) - len(merged) if exclude_biotech else 0,
    }


def _safe_int(v) -> int:
    try:
        if isinstance(v, str):
            v = v.replace(",", "").replace("$", "").strip()
        f = float(v)
        if pd.isna(f):
            return 0
        return int(f)
    except (ValueError, TypeError):
        return 0


def _safe_float(v) -> float:
    try:
        if isinstance(v, str):
            v = v.replace(",", "").replace("$", "").strip()
        f = float(v)
        if pd.isna(f):
            return 0.0
        return f
    except (ValueError, TypeError):
        return 0.0


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------
def cmd_summary(args):
    company = _resolve_institution(args.institution)
    offset = _get_offset(args, company)
    thirteenf = _retry(lambda: company.get_filings(form="13F-HR")[offset].obj())

    data = {
        "manager": thirteenf.management_company_name,
        "report_period": str(thirteenf.report_period),
        "holdings": int(thirteenf.total_holdings),
        "total_value": float(thirteenf.total_value),
        "signer": str(thirteenf.signer),
    }
    _emit({"ok": True, "institution": args.institution, "offset": offset, "summary": data}, args.json)


def cmd_top(args):
    company = _resolve_institution(args.institution)
    offset = _get_offset(args, company)
    thirteenf = _retry(lambda: company.get_filings(form="13F-HR")[offset].obj())
    holdings = thirteenf.holdings
    top_n = holdings.nlargest(args.limit, "Value")

    rows = []
    for _, row in top_n.iterrows():
        rows.append({
            "ticker": str(row.get("Ticker", "")),
            "issuer": str(row.get("Issuer", "")),
            "shares": _safe_int(row.get("SharesPrnAmount", 0)),
            "value": _safe_float(row.get("Value", 0)),
        })
    _emit({
        "ok": True, "institution": args.institution, "offset": offset,
        "report_period": str(thirteenf.report_period),
        "rows": rows,
    }, args.json)


def cmd_compare(args):
    company = _resolve_institution(args.institution)
    offset = _get_offset(args, company)
    thirteenf = _retry(lambda: company.get_filings(form="13F-HR")[offset].obj())
    comparison = _retry(lambda: thirteenf.compare_holdings())

    # Extract rows (stable path: HoldingsComparison.data is a DataFrame)
    rows = []
    try:
        df = getattr(comparison, "data", None)
        if isinstance(df, pd.DataFrame) and not df.empty:
            rows = df.to_dict(orient="records")
        elif hasattr(comparison, "to_pandas"):
            df2 = comparison.to_pandas()
            if isinstance(df2, pd.DataFrame) and not df2.empty:
                rows = df2.to_dict(orient="records")
    except Exception:
        rows = []

    result = {
        "ok": True,
        "institution": args.institution,
        "offset": offset,
        "manager": thirteenf.management_company_name,
        "base_period": str(thirteenf.report_period),
        "rows": rows,
        "raw_text": str(comparison),
    }

    # Auto-format if requested (#1)
    if args.format == "cn" and rows:
        report = _build_report(rows, exclude_biotech=not args.include_biotech)
        result["formatted_report"] = report["report_text"]
        result["categories"] = report["categories"]
        result["total_positions"] = report["total_positions"]
        result["filtered_biotech"] = report["filtered_biotech"]

    _emit(result, args.json)


def cmd_search(args):
    """Search institution by name."""
    query = args.query.lower().strip()
    matches = []
    for name, cik in _INSTITUTION_MAP.items():
        if name.startswith("_"):
            continue
        if query in name.lower():
            matches.append({"name": name, "cik": cik})

    if matches:
        _emit({"ok": True, "query": args.query, "matches": matches}, args.json)
    else:
        _emit({"ok": False, "query": args.query, "error": "No matching institution found.",
               "hint": "Try a shorter name, or use CIK directly. Edit institution_map.json to add new entries."}, args.json)


def cmd_self_test(args):
    checks = []
    checks.append({"name": "env.EDGAR_IDENTITY", "ok": bool(os.environ.get("EDGAR_IDENTITY"))})
    checks.append({"name": "classification.json", "ok": bool(_CLASSIFICATION)})
    checks.append({"name": "merge_rules.json", "ok": bool(_MERGE_RULES)})
    checks.append({"name": "institution_map.json", "ok": bool(_INSTITUTION_MAP)})

    try:
        company = _resolve_institution(args.institution)
        checks.append({"name": "institution.lookup", "ok": True})
        thirteenf = _retry(lambda: company.get_filings(form="13F-HR")[0].obj())
        checks.append({"name": "13f.latest", "ok": True, "period": str(thirteenf.report_period)})
    except Exception as e:
        checks.append({"name": "institution/13f", "ok": False, "error": str(e), "hint": _error_hint(str(e))})

    ok = all(c.get("ok") for c in checks)
    _emit({"ok": ok, "checks": checks}, args.json)


def _get_offset(args, company=None) -> int:
    """Get offset from args, supporting both --offset and --quarter."""
    if hasattr(args, "quarter") and args.quarter:
        if company is None:
            raise RuntimeError("Company required for --quarter resolution")
        return _quarter_to_offset(args.quarter, company)
    return getattr(args, "offset", 0)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="SEC 13F Analyzer v2")
    parser.add_argument("--json", action="store_true", help="JSON output")
    sub = parser.add_subparsers(dest="command", required=True)

    # Shared args
    parent = argparse.ArgumentParser(add_help=False)
    parent.add_argument("--institution", required=True,
                        help="Ticker, CIK, or name (e.g., 'HHLR', '0001762304', 'berkshire')")
    parent.add_argument("--offset", type=int, default=0,
                        help="0=latest quarter, 1=previous, etc.")
    parent.add_argument("--quarter", type=str, default="",
                        help="Quarter string e.g. '25Q4', '2025Q3' (alternative to --offset)")

    # summary
    p = sub.add_parser("summary", parents=[parent])
    p.set_defaults(func=cmd_summary)

    # top
    p = sub.add_parser("top", parents=[parent])
    p.add_argument("--limit", type=int, default=10)
    p.set_defaults(func=cmd_top)

    # compare
    p = sub.add_parser("compare", parents=[parent])
    p.add_argument("--format", choices=["raw", "cn"], default="cn",
                    help="Output format: 'raw'=data only, 'cn'=auto-formatted Chinese report (default)")
    p.add_argument("--include-biotech", action="store_true",
                    help="Include biotech companies (excluded by default)")
    p.set_defaults(func=cmd_compare)

    # search
    p = sub.add_parser("search")
    p.add_argument("--query", required=True, help="Institution name to search")
    p.set_defaults(func=cmd_search)

    # self-test
    p = sub.add_parser("self-test")
    p.add_argument("--institution", default="0001067983")
    p.set_defaults(func=cmd_self_test)

    args = parser.parse_args()
    try:
        args.func(args)
    except Exception as e:
        _emit({"ok": False, "error": str(e), "hint": _error_hint(str(e))}, getattr(args, "json", False))
        sys.exit(1)


if __name__ == "__main__":
    main()
