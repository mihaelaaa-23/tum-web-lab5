#!/usr/bin/env python3

import sys
import argparse


def build_parser():
    parser = argparse.ArgumentParser(
        prog="go2web",
        description="A CLI tool to make raw HTTP requests and search the web.",
        add_help=False,  # we handle -h manually for full control
    )
    parser.add_argument("-u", metavar="URL", help="Make an HTTP request to URL and print the response")
    parser.add_argument("-s", metavar="SEARCH_TERM", nargs="+", help="Search for SEARCH_TERM and print top 10 results")
    return parser


def print_help():
    help_text = """go2web - a minimal HTTP CLI tool

Usage:
  go2web -h                        Show this help message
  go2web -u <URL>                  Fetch URL and print human-readable response
  go2web -s <search-term>          Search and print top 10 results

Examples:
  go2web -u http://example.com
  go2web -s python web scraping
"""
    print(help_text)


def main():
    parser = build_parser()
    args, unknown = parser.parse_known_args()

    if args.h or len(sys.argv) == 1 or "-h" in unknown:
        print_help()
        sys.exit(0)

    if args.u:
        print(f"[stub] Would fetch: {args.u}")

    if args.s:
        term = " ".join(args.s)
        print(f"[stub] Would search for: {term}")


if __name__ == "__main__":
    main()