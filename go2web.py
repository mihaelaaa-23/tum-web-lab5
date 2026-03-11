#!/usr/bin/env python3

import sys
import argparse
import socket


def build_parser():
    parser = argparse.ArgumentParser(
        prog="go2web",
        description="A CLI tool to make raw HTTP requests and search the web.",
        add_help=False,
    )
    parser.add_argument("-h", dest="show_help", action="store_true", help="Show this help message and exit")
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


def fetch_url(url):
    # Parse URL manually — no urllib
    if url.startswith("https://"):
        print("HTTPS not supported yet (requires SSL). Use http://")
        sys.exit(1)

    url = url.removeprefix("http://")
    host, _, path = url.partition("/")
    path = "/" + path if path else "/"

    # Open raw TCP socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((host, 80))

    request = (
        f"GET {path} HTTP/1.1\r\n"
        f"Host: {host}\r\n"
        f"Connection: close\r\n"
        f"\r\n"
    )
    sock.sendall(request.encode())

    # Read full response
    response = b""
    while True:
        chunk = sock.recv(4096)
        if not chunk:
            break
        response += chunk

    sock.close()
    return response.decode("utf-8", errors="replace")

def main():
    parser = build_parser()
    args = parser.parse_args()

    if args.show_help or len(sys.argv) == 1:
        print_help()
        sys.exit(0)

    if args.u:
        raw = fetch_url(args.u)
        print(raw)          # prints everything for now — headers + body

    if args.s:
        term = " ".join(args.s)
        print(f"[stub] Would search for: {term}")


if __name__ == "__main__":
    main()