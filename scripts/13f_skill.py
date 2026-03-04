#!/usr/bin/env python3
import argparse
import json
import os
import sys

import pandas as pd
from edgar import Company, set_identity

pd.set_option('display.max_rows', None)
pd.set_option('display.max_columns', None)
pd.set_option('display.width', 2000)
pd.set_option('display.max_colwidth', None)


def emit_json(payload):
    print(json.dumps(payload, ensure_ascii=False, default=str))


def error_hint(msg: str) -> str:
    m = (msg or "").lower()
    if "edgar_identity" in m or "user-agent" in m:
        return "Set EDGAR_IDENTITY, e.g. export EDGAR_IDENTITY='Your Name <you@example.com>'"
    if "not enough 13f filings history" in m:
        return "Reduce --offset or verify the institution has enough 13F history."
    if "ssl" in m or "tls" in m or "unexpected_eof_while_reading" in m:
        return "Network/TLS issue. Check proxy settings and access to data.sec.gov."
    if "finding institution" in m:
        return "Use a valid ticker or numeric CIK."
    return "Check parameters and network; then retry."


def print_error(prefix: str, err: Exception, as_json: bool = False):
    if as_json:
        emit_json({"ok": False, "error": str(err), "hint": error_hint(str(err))})
    else:
        print(f"{prefix}: {err}")
        print(f"Hint: {error_hint(str(err))}")


if "EDGAR_IDENTITY" in os.environ:
    set_identity(os.environ["EDGAR_IDENTITY"])
else:
    print("WARNING: EDGAR_IDENTITY environment variable is not set. SEC requires a valid User-Agent. Please export EDGAR_IDENTITY='Name <email@example.com>'")
    set_identity("OpenClaw_Agent <bot@openclaw.ai>")


def get_institution(identifier):
    try:
        return Company(int(identifier)) if identifier.isdigit() else Company(identifier)
    except Exception as e:
        raise RuntimeError(f"Error finding institution '{identifier}': {e}") from e


def get_13f_obj(company, offset=0):
    try:
        filings = company.get_filings(form="13F-HR")
        if len(filings) <= offset:
            raise RuntimeError(f"Not enough 13F filings history. Requested index {offset}, but only {len(filings)} found.")
        return filings[offset].obj()
    except RuntimeError:
        raise
    except Exception as e:
        raise RuntimeError(f"Error retrieving 13F filing: {e}") from e


def command_summary(args):
    company = get_institution(args.institution)
    thirteenf = get_13f_obj(company, args.offset)
    data = {
        "manager": thirteenf.management_company_name,
        "report_period": str(thirteenf.report_period),
        "holdings": int(thirteenf.total_holdings),
        "total_value": float(thirteenf.total_value),
        "signer": str(thirteenf.signer),
    }

    if args.json:
        emit_json({"ok": True, "institution": args.institution, "offset": args.offset, "summary": data})
        return

    print(f"Manager:        {data['manager']}")
    print(f"Report period:  {data['report_period']}")
    print(f"Holdings:       {data['holdings']}")
    print(f"Total value:    ${data['total_value']:,.0f}")
    print(f"Signed by:      {data['signer']}")


def command_top(args):
    company = get_institution(args.institution)
    thirteenf = get_13f_obj(company, args.offset)
    holdings = thirteenf.holdings
    top_n = holdings.nlargest(args.limit, "Value")

    if args.json:
        rows = []
        for _, row in top_n.iterrows():
            rows.append({
                "ticker": row.get("Ticker"),
                "issuer": row.get("Issuer"),
                "shares": int(row.get("SharesPrnAmount", 0)),
                "value": float(row.get("Value", 0)),
            })
        emit_json({
            "ok": True,
            "institution": args.institution,
            "offset": args.offset,
            "report_period": str(thirteenf.report_period),
            "rows": rows,
        })
        return

    print(f"\nTop {args.limit} Holdings for {thirteenf.management_company_name} ({thirteenf.report_period}):")
    print("-" * 80)
    for _, row in top_n.iterrows():
        print(f"{row['Ticker']:6s}  {row['Issuer']:30s}  {row['SharesPrnAmount']:>15,} shares  ${row['Value']:>18,.0f}")


def command_compare(args):
    company = get_institution(args.institution)
    thirteenf = get_13f_obj(company, args.offset)
    comparison = thirteenf.compare_holdings()

    if args.json:
        rows = []
        try:
            df = comparison.to_pandas() if hasattr(comparison, "to_pandas") else None
            if df is not None:
                rows = df.to_dict(orient="records")
        except Exception:
            rows = []

        emit_json({
            "ok": True,
            "institution": args.institution,
            "offset": args.offset,
            "manager": thirteenf.management_company_name,
            "base_period": str(thirteenf.report_period),
            "raw_text": str(comparison),
            "rows": rows,
        })
        return

    print(f"Data Context: Comparison for {thirteenf.management_company_name}")
    print(f"Base Period: {thirteenf.report_period}")
    print("--- RAW DATA START ---")
    print(str(comparison))
    print("--- RAW DATA END ---")


def command_self_test(args):
    checks = []

    checks.append({"name": "env.EDGAR_IDENTITY", "ok": bool(os.environ.get("EDGAR_IDENTITY"))})

    try:
        company = get_institution(args.institution)
        checks.append({"name": "institution.lookup", "ok": True, "institution": args.institution})
        _ = get_13f_obj(company, 0)
        checks.append({"name": "13f.latest", "ok": True})
    except Exception as e:
        checks.append({"name": "institution.lookup/13f.latest", "ok": False, "error": str(e), "hint": error_hint(str(e))})

    ok = all(c.get("ok") for c in checks)
    if args.json:
        emit_json({"ok": ok, "checks": checks})
    else:
        print(f"Self-test for {args.institution}: {'PASS' if ok else 'FAIL'}")
        for c in checks:
            if c["ok"]:
                print(f"  [PASS] {c['name']}")
            else:
                print(f"  [FAIL] {c['name']}: {c.get('error')}")
                print(f"         hint: {c.get('hint')}")


def main():
    parser = argparse.ArgumentParser(description='SEC 13F Analyzer for OpenClaw using EdgarTools')
    parser.add_argument('--json', action='store_true', help='Output machine-readable JSON')
    subparsers = parser.add_subparsers(dest='command', required=True)

    parent_parser = argparse.ArgumentParser(add_help=False)
    parent_parser.add_argument('--institution', required=True, help='Ticker or CIK of the institution (e.g., BRK.B, 1697748)')
    parent_parser.add_argument('--offset', type=int, default=0, help='0=Latest quarter, 1=Previous quarter, etc. (default: 0)')

    parser_summary = subparsers.add_parser('summary', parents=[parent_parser], help='Get portfolio summary')
    parser_summary.set_defaults(func=command_summary)

    parser_top = subparsers.add_parser('top', parents=[parent_parser], help='Get top N holdings')
    parser_top.add_argument('--limit', type=int, default=10, help='Number of top holdings (default: 10)')
    parser_top.set_defaults(func=command_top)

    parser_compare = subparsers.add_parser('compare', parents=[parent_parser], help='Compare quarter-over-quarter holdings')
    parser_compare.set_defaults(func=command_compare)

    parser_self = subparsers.add_parser('self-test', help='Run health checks')
    parser_self.add_argument('--institution', default='0001067983', help='Ticker or CIK used for connectivity test')
    parser_self.set_defaults(func=command_self_test)

    args = parser.parse_args()
    try:
        args.func(args)
    except Exception as e:
        print_error('Error', e, as_json=getattr(args, 'json', False))
        sys.exit(1)


if __name__ == '__main__':
    main()
