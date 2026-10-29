"""deadlinks: find broken http(s) links in Markdown, reStructuredText and Python docs.

Usage: python deadlinks.py PATH [PATH ...] [--timeout 10] [--workers 16] [--ignore REGEX]
Exit code is 1 if any dead link is found, 0 otherwise.
"""
import argparse
import concurrent.futures as cf
import http.client
import os
import re
import sys
import urllib.error
import urllib.request

EXTENSIONS = (".md", ".rst", ".txt", ".py")
URL_RE = re.compile(r"https?://[^\s<>\]\"'`]+")
SKIP_DIRS = {".git", "node_modules", "_build", "build", "dist", ".venv", "venv"}
# Hosts that are placeholders in docs and never resolve to real pages.
PLACEHOLDER_HOSTS = {"example.com", "example.org", "example.net", "localhost", "127.0.0.1", "0.0.0.0"}


def extract_urls(text):
    """Return a list of (line_number, url) found in text."""
    found = []
    for number, line in enumerate(text.splitlines(), 1):
        for match in URL_RE.findall(line):
            url = match.rstrip(".,;:!?*_")
            while url.endswith(")") and url.count("(") < url.count(")"):
                url = url[:-1].rstrip(".,;:!?*_")
            found.append((number, url))
    return found


def is_placeholder(url):
    host = re.sub(r"^https?://", "", url).split("/")[0].split(":")[0].lower()
    return host in PLACEHOLDER_HOSTS or host.endswith(".example.com") or "{" in url or "<" in url


def iter_files(paths):
    for path in paths:
        if os.path.isfile(path):
            yield path
            continue
        for root, dirs, files in os.walk(path):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            for name in sorted(files):
                if name.endswith(EXTENSIONS):
                    yield os.path.join(root, name)


def check_url(url, timeout=10):
    """Return an HTTP status code, or None if the host could not be reached."""
    headers = {"User-Agent": "Mozilla/5.0 (deadlinks)"}
    for method in ("HEAD", "GET"):
        request = urllib.request.Request(url, method=method, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.status
        except urllib.error.HTTPError as error:
            if method == "HEAD" and error.code in (403, 404, 405, 501):
                continue  # some servers reject HEAD; confirm with GET
            return error.code
        except (urllib.error.URLError, http.client.HTTPException, TimeoutError, ValueError, OSError):
            return None
    return None


def find_dead(paths, timeout=10, workers=16, ignore=None, checker=check_url):
    """Return a sorted list of (file, line, url, status) for links answering 404 or 410."""
    ignore_re = re.compile(ignore) if ignore else None
    first_seen = {}
    for path in iter_files(paths):
        with open(path, encoding="utf-8", errors="ignore") as handle:
            for number, url in extract_urls(handle.read()):
                if is_placeholder(url) or (ignore_re and ignore_re.search(url)):
                    continue
                first_seen.setdefault(url, (path, number))
    urls = list(first_seen)
    with cf.ThreadPoolExecutor(workers) as pool:
        statuses = list(pool.map(lambda u: checker(u, timeout), urls))
    dead = [(*first_seen[u], u, s) for u, s in zip(urls, statuses) if s in (404, 410)]
    return sorted(dead)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("paths", nargs="+")
    parser.add_argument("--timeout", type=float, default=10)
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--ignore", help="regex of URLs to skip")
    args = parser.parse_args(argv)
    dead = find_dead(args.paths, args.timeout, args.workers, args.ignore)
    for path, line, url, status in dead:
        print(f"{path}:{line}: {status} {url}")
    print(f"{len(dead)} dead link(s)")
    return 1 if dead else 0


if __name__ == "__main__":
    sys.exit(main())
