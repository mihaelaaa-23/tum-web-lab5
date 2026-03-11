#!/usr/bin/env python3

import sys
import argparse
import socket
import re

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

def parse_response(raw):
    # Split headers and body on the blank line
    if "\r\n\r\n" in raw:
        headers_part, body = raw.split("\r\n\r\n", 1)
    else:
        headers_part, body = raw, ""

    header_lines = headers_part.split("\r\n")
    status_line = header_lines[0]
    headers = {}
    for line in header_lines[1:]:
        if ":" in line:
            key, _, value = line.partition(":")
            headers[key.strip().lower()] = value.strip()

    # Handle chunked transfer encoding
    if headers.get("transfer-encoding") == "chunked":
        body = decode_chunked(body)

    return status_line, headers, body


def decode_chunked(data):
    result = ""
    while data:
        # Each chunk: hex size line, then data
        line_end = data.find("\r\n")
        if line_end == -1:
            break
        chunk_size = int(data[:line_end], 16)
        if chunk_size == 0:
            break
        result += data[line_end + 2: line_end + 2 + chunk_size]
        data = data[line_end + 2 + chunk_size + 2:]
    return result

def strip_html(html):
    # Remove <script> and <style> blocks entirely
    html = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", html, flags=re.DOTALL | re.IGNORECASE)
    # Replace block-level tags with newlines for readability
    html = re.sub(r"<(br|p|div|h[1-6]|li|tr)[^>]*>", "\n", html, flags=re.IGNORECASE)
    # Strip all remaining tags
    html = re.sub(r"<[^>]+>", "", html)
    # Decode common HTML entities
    html = html.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    html = html.replace("&nbsp;", " ").replace("&quot;", '"').replace("&#39;", "'")
    # Collapse blank lines
    html = re.sub(r"\n{3,}", "\n\n", html)
    return html.strip()

def main():
    parser = build_parser()
    args = parser.parse_args()

    if args.show_help or len(sys.argv) == 1:
        print_help()
        sys.exit(0)

    if args.u:
        raw = fetch_url(args.u)
        status, headers, body = parse_response(raw)
        print(f"Status: {status}\n")
        print(strip_html(body))

    if args.s:
        term = " ".join(args.s)
        print(f"[stub] Would search for: {term}")


if __name__ == "__main__":
    main()