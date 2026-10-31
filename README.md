# deadlinks

A small, dependency-free command line tool that finds broken `http(s)` links in documentation.
It scans Markdown, reStructuredText, text and Python files and reports links that answer
`404` or `410`.

```
python deadlinks.py docs/ README.md --ignore 'localhost|internal\.corp'
docs/guide.md:42: 404 https://example.org/old-page
1 dead link(s)
```

- Checks each unique URL once and reports its first location.
- Skips placeholder hosts (`example.com`, `localhost`) and templated URLs like `https://x.org/{id}`.
- Tries `HEAD` first and falls back to `GET` for servers that reject `HEAD`.
- Network errors and timeouts are not reported as dead, to avoid false alarms.
- Can also report links that redirect (`--moved`) so they can be updated to their final address.
- Exit code `1` when dead links exist, so it works in CI.

Options: `--timeout SECONDS` (default 10), `--workers N` (default 16), `--ignore REGEX`, `--json` (machine-readable output), `--moved` (report redirected links).

## Tests

```
pip install pytest
pytest
```

Python 3.8+. MIT licensed.
