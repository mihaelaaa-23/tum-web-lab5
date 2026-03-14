#!/usr/bin/env python3

import sys
import argparse
import socket
import re
import ssl

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
    if url.startswith("https://"):
        use_ssl = True
        url = url.removeprefix("https://")
        default_port = 443
    else:
        use_ssl = False
        url = url.removeprefix("http://")
        default_port = 80

    host, _, path = url.partition("/")
    path = "/" + path if path else "/"

    if ":" in host:
        host, port_str = host.rsplit(":", 1)
        port = int(port_str)
    else:
        port = default_port

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    if use_ssl:
        context = ssl.create_default_context()
        sock = context.wrap_socket(sock, server_hostname=host)

    sock.connect((host, port))

    request = (
        f"GET {path} HTTP/1.1\r\n"
        f"Host: {host}\r\n"
        f"Connection: close\r\n"
        f"User-Agent: Mozilla/5.0\r\n"
        f"\r\n"
    )
    sock.sendall(request.encode())

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

def decode_entities(text):
    text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    text = text.replace("&nbsp;", " ").replace("&quot;", '"').replace("&#39;", "'")
    text = re.sub(r'&#x([0-9A-Fa-f]+);', lambda m: chr(int(m.group(1), 16)), text)
    text = re.sub(r'&#(\d+);', lambda m: chr(int(m.group(1))), text)
    return text

def parse_search_results(html):
    results = []

    # Extract each result block
    titles = re.findall(r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', html, re.DOTALL)
    snippets = re.findall(r'class="result__snippet"[^>]*>(.*?)</a>', html, re.DOTALL)

    for i, (href, title) in enumerate(titles[:10]):
        # Decode the real URL from uddg= parameter
        url_match = re.search(r'uddg=(https?[^&]+)', href)
        url = url_match.group(1) if url_match else href
        # URL-decode %2F etc.
        url = re.sub(r'%([0-9A-Fa-f]{2})', lambda m: chr(int(m.group(1), 16)), url)

        title = decode_entities(re.sub(r'<[^>]+>', '', title).strip())

        snippet = ""
        if i < len(snippets):
            snippet = decode_entities(re.sub(r'<[^>]+>', '', snippets[i]).strip())

        results.append((title, url, snippet))

    return results

def decode_chunked(data):
    result = ""
    while data:
        line_end = data.find("\r\n")
        if line_end == -1:
            break
        size_str = data[:line_end].strip()
        if not size_str:
            data = data[2:]
            continue
        try:
            chunk_size = int(size_str, 16)
        except ValueError:
            # Not actually chunked encoding — return data as-is
            return data
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

def search(term):
    query = term.replace(" ", "+")
    url = f"https://html.duckduckgo.com/html/?q={query}"
    return fetch_url(url)

def main():
    parser = build_parser()
    args = parser.parse_args()

    if args.show_help or len(sys.argv) == 1:
        print_help()
        sys.exit(0)

    if args.u:
        try:
            raw = fetch_url(args.u)
            status, headers, body = parse_response(raw)
            print(f"Status: {status}\n")
            print(strip_html(body))
        except ConnectionRefusedError:
            print(f"Error: connection refused for {args.u}")
            sys.exit(1)
        except socket.gaierror as e:
            print(f"Error: could not resolve host — {e}")
            sys.exit(1)
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)

    if args.s:
        term = " ".join(args.s)
        raw = search(term)
        status, headers, body = parse_response(raw)
        results = parse_search_results(body)
        for i, (title, url, snippet) in enumerate(results, 1):
            print(f"{i}. {title}")
            print(f"   {url}")
            if snippet:
                print(f"   {snippet}")
            print()


if __name__ == "__main__":
    main()