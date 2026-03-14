#!/usr/bin/env python3

import sys
import argparse
import socket
import re
import ssl

_cache = {}

def build_parser():
    parser = argparse.ArgumentParser(
        prog="go2web",
        description="A CLI tool to make raw HTTP requests and search the web.",
        add_help=False,
    )
    parser.add_argument("-h", dest="show_help", action="store_true", help="Show this help message and exit")
    parser.add_argument("-u", metavar="URL", help="Make an HTTP request to URL and print the response")
    parser.add_argument("-s", metavar="SEARCH_TERM", nargs="+", help="Search and print top 10 results. Append a number to fetch that result.")
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


def fetch_url(url, max_redirects=5):
    if url in _cache:
        print(f"[cache hit] {url}", file=sys.stderr)
        return _cache[url]
    
    for _ in range(max_redirects):
        if url.startswith("https://"):
            use_ssl = True
            url_stripped = url.removeprefix("https://")
            default_port = 443
        else:
            use_ssl = False
            url_stripped = url.removeprefix("http://")
            default_port = 80

        host, _, path = url_stripped.partition("/")
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

        raw = response.decode("utf-8", errors="replace")
        status_line, headers, body = parse_response(raw)
        status_code = int(status_line.split()[1])

        if status_code in (301, 302, 303, 307, 308) and "location" in headers:
            url = headers["location"]
            # Handle relative redirects
            if url.startswith("/"):
                base = "https://" if use_ssl else "http://"
                url = base + host + url
            continue

        _cache[url] = raw
        return raw

    print(f"Error: too many redirects")
    sys.exit(1)

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
    if headers.get("transfer-encoding") == "chunked" or re.match(r'^[0-9a-fA-F]+\r\n', body):
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
    seen_urls = set()

    blocks = re.findall(r'<div[^>]+class="[^"]*algo[^"]*"[^>]*>(.*?)</div>\s*</div>\s*</div>', html, re.DOTALL)

    for block in blocks:
        title_match = re.search(r'<h3[^>]*>.*?<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', block, re.DOTALL)
        snippet_match = re.search(r'<p[^>]*>(.*?)</p>', block, re.DOTALL)

        if not title_match:
            continue

        href = title_match.group(1)
        title = decode_entities(re.sub(r'<[^>]+>', '', title_match.group(2)).strip())
        title = re.sub(r'^.*?›\s*', '', title).strip()

        # Extract real URL from Yahoo redirect
        url_match = re.search(r'RU=([^/]+)', href)
        if url_match:
            import urllib.parse
            url = urllib.parse.unquote(url_match.group(1))
        else:
            url = href

        # Skip Yahoo-internal URLs and duplicates
        if not url.startswith("http") or "yahoo.com" in url or url in seen_urls:
            continue

        snippet = ""
        if snippet_match:
            snippet = decode_entities(re.sub(r'<[^>]+>', '', snippet_match.group(1)).strip())

        seen_urls.add(url)
        results.append((title, url, snippet))

        if len(results) == 10:
            break

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
            return data  # not chunked, return as-is
        if chunk_size == 0:
            break
        result += data[line_end + 2: line_end + 2 + chunk_size]
        data = data[line_end + 2 + chunk_size + 2:]
    return result

def strip_html(html):
    html = re.sub(r'^[0-9a-fA-F]+\s*$', '', html, flags=re.MULTILINE)
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
    host = "search.yahoo.com"
    path = f"/search?p={query}&ei=UTF-8"

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    context = ssl.create_default_context()
    sock = context.wrap_socket(sock, server_hostname=host)
    sock.connect((host, 443))

    request = (
        f"GET {path} HTTP/1.1\r\n"
        f"Host: {host}\r\n"
        f"Connection: close\r\n"
        f"User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36\r\n"
        f"Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8\r\n"
        f"Accept-Language: en-US,en;q=0.5\r\n"
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
        tokens = args.s
        index = None
        if tokens[-1].isdigit():
            index = int(tokens[-1])
            tokens = tokens[:-1]

        term = " ".join(tokens)
        raw = search(term)
        status, headers, body = parse_response(raw)
        results = parse_search_results(body)

        if not results:
            print("No results found.")
            sys.exit(1)

        if index is not None:
            if 1 <= index <= len(results):
                title, url, snippet = results[index - 1]
                print(f"Fetching result {index}: {title}")
                print(f"URL: {url}\n")
                raw2 = fetch_url(url)
                status2, headers2, body2 = parse_response(raw2)
                print(f"Status: {status2}\n")
                print(strip_html(body2))
            else:
                print(f"Error: index {index} out of range (1-{len(results)})")
                sys.exit(1)
        else:
            for i, (title, url, snippet) in enumerate(results, 1):
                print(f"{i}. {title}")
                print(f"   {url}")
                if snippet:
                    print(f"   {snippet}")
                print()


if __name__ == "__main__":
    main()