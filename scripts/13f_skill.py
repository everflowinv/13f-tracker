#!/usr/bin/env python3
import argparse
import sys
import os
import pandas as pd
from edgar import Company, set_identity

pd.set_option('display.max_rows', None)
pd.set_option('display.max_columns', None)
pd.set_option('display.width', 2000)
pd.set_option('display.max_colwidth', None)

# 设置 SEC 要求的身份标识
if "EDGAR_IDENTITY" in os.environ:
    set_identity(os.environ["EDGAR_IDENTITY"])
else:
    print("WARNING: EDGAR_IDENTITY environment variable is not set. SEC requires a valid User-Agent. Please export EDGAR_IDENTITY='Name <email@example.com>'")
    set_identity("OpenClaw_Agent <bot@openclaw.ai>")

def get_institution(identifier):
    """通过 CIK (数字) 或 Ticker/名称获取机构对象"""
    try:
        if identifier.isdigit():
            return Company(int(identifier))
        else:
            return Company(identifier)
    except Exception as e:
        print(f"Error finding institution '{identifier}': {e}")
        sys.exit(1)

def get_13f_obj(company, offset=0):
    """
    获取 13F 对象。offset=0 为最新一期，offset=1 为上一期，以此类推。
    由于 13F-HR 通常是按季度发布，offset 直接对应回溯的季度数。
    """
    try:
        filings = company.get_filings(form="13F-HR")
        if len(filings) <= offset:
            print(f"Error: Not enough 13F filings history. Requested index {offset}, but only {len(filings)} found.")
            sys.exit(1)
        return filings[offset].obj()
    except Exception as e:
        print(f"Error retrieving 13F filing: {e}")
        sys.exit(1)

def command_summary(args):
    """输出组合概览"""
    company = get_institution(args.institution)
    thirteenf = get_13f_obj(company, args.offset)
    
    print(f"Manager:        {thirteenf.management_company_name}")
    print(f"Report period:  {thirteenf.report_period}")
    print(f"Holdings:       {thirteenf.total_holdings}")
    print(f"Total value:    ${thirteenf.total_value:,.0f}")
    print(f"Signed by:      {thirteenf.signer}")

def command_top(args):
    """输出前 N 大重仓股"""
    company = get_institution(args.institution)
    thirteenf = get_13f_obj(company, args.offset)
    
    # 转换为 DataFrame 并排序
    holdings = thirteenf.holdings
    top_n = holdings.nlargest(args.limit, "Value")
    
    print(f"\nTop {args.limit} Holdings for {thirteenf.management_company_name} ({thirteenf.report_period}):")
    print("-" * 80)
    for _, row in top_n.iterrows():
        print(f"{row['Ticker']:6s}  {row['Issuer']:30s}  {row['SharesPrnAmount']:>15,} shares  ${row['Value']:>18,.0f}")

def command_compare(args):
    """
    输出干净的对比数据供大模型读取
    """
    company = get_institution(args.institution)
    thirteenf = get_13f_obj(company, args.offset)
    
    comparison = thirteenf.compare_holdings()
    
    # 打印前置信息和表格纯文本
    print(f"Data Context: Comparison for {thirteenf.management_company_name}")
    print(f"Base Period: {thirteenf.report_period}")
    print("--- RAW DATA START ---")
    print(str(comparison))
    print("--- RAW DATA END ---")

def main():
    parser = argparse.ArgumentParser(description='SEC 13F Analyzer for OpenClaw using EdgarTools')
    subparsers = parser.add_subparsers(dest='command', required=True)
    
    # 公共参数
    parent_parser = argparse.ArgumentParser(add_help=False)
    parent_parser.add_argument('--institution', required=True, help='Ticker or CIK of the institution (e.g., BRK.B, 1697748)')
    parent_parser.add_argument('--offset', type=int, default=0, help='0=Latest quarter, 1=Previous quarter, etc. (default: 0)')

    # 子命令定义
    parser_summary = subparsers.add_parser('summary', parents=[parent_parser], help='Get portfolio summary')
    parser_summary.set_defaults(func=command_summary)
    
    parser_top = subparsers.add_parser('top', parents=[parent_parser], help='Get top N holdings')
    parser_top.add_argument('--limit', type=int, default=10, help='Number of top holdings (default: 10)')
    parser_top.set_defaults(func=command_top)
    
    parser_compare = subparsers.add_parser('compare', parents=[parent_parser], help='Compare quarter-over-quarter holdings')
    parser_compare.set_defaults(func=command_compare)

    args = parser.parse_args()
    args.func(args)

if __name__ == '__main__':
    main()
