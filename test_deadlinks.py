import pytest

import deadlinks


def test_extract_urls_strips_trailing_punctuation():
    text = "See https://a.org/x. And (https://b.org/y), plus [t](https://c.org/z)"
    urls = [u for _, u in deadlinks.extract_urls(text)]
    assert urls == ["https://a.org/x", "https://b.org/y", "https://c.org/z"]


def test_extract_urls_keeps_balanced_parens():
    text = "https://en.wikipedia.org/wiki/RSA_(cryptosystem)"
    assert deadlinks.extract_urls(text) == [(1, text)]


def test_placeholders_are_skipped():
    assert deadlinks.is_placeholder("http://localhost:8000/x")
    assert deadlinks.is_placeholder("https://example.com/a")
    assert deadlinks.is_placeholder("https://x.org/{id}")
    assert not deadlinks.is_placeholder("https://python.org/")


def _checker(codes):
    return lambda u, t: (codes.get(u, 200), u)


def test_find_dead_reports_only_404_and_410(tmp_path):
    (tmp_path / "doc.md").write_text(
        "ok https://ok.test/a\ngone https://gone.test/b\nold https://old.test/c\n"
        "slow https://down.test/d\nskip https://skip.test/e\n"
    )
    codes = {"https://ok.test/a": 200, "https://gone.test/b": 404,
             "https://old.test/c": 410, "https://down.test/d": None}
    dead, moved = deadlinks.find_dead(
        [str(tmp_path)], ignore="skip.test", checker=_checker(codes)
    )
    assert [(line, url, status) for _, line, url, status in dead] == [
        (2, "https://gone.test/b", 404), (3, "https://old.test/c", 410)]
    assert moved == []


def test_moved_links_are_reported(tmp_path):
    (tmp_path / "doc.md").write_text(
        "old https://old.test/page\nfine https://fine.test/page\n"
    )
    finals = {"https://old.test/page": "https://new.test/page"}
    checker = lambda u, t: (200, finals.get(u, u))
    dead, moved = deadlinks.find_dead([str(tmp_path)], checker=checker)
    assert dead == []
    assert moved == [(str(tmp_path / "doc.md"), 1, "https://old.test/page", "https://new.test/page")]


def test_trailing_slash_redirect_is_not_moved(tmp_path):
    (tmp_path / "doc.md").write_text("link https://x.test/page\n")
    checker = lambda u, t: (200, u + "/")
    dead, moved = deadlinks.find_dead([str(tmp_path)], checker=checker)
    assert dead == [] and moved == []


def test_each_url_reported_once_at_first_location(tmp_path):
    (tmp_path / "a.md").write_text("https://gone.test/x\n")
    (tmp_path / "b.md").write_text("\nhttps://gone.test/x\n")
    dead, moved = deadlinks.find_dead([str(tmp_path)], checker=lambda u, t: (404, u))
    assert len(dead) == 1 and dead[0][0].endswith("a.md")


def test_main_exit_code(tmp_path, capsys, monkeypatch):
    (tmp_path / "a.md").write_text("https://gone.test/x\n")
    monkeypatch.setattr(deadlinks, "check_url", lambda u, t=10: (404, u))
    monkeypatch.setattr(deadlinks, "find_dead",
                        lambda *a, **k: ([("a.md", 1, "https://gone.test/x", 404)], []))
    assert deadlinks.main([str(tmp_path)]) == 1
    assert "1 dead link(s)" in capsys.readouterr().out


def test_check_url_survives_malformed_url():
    url = "https://host:%d%s/path"
    assert deadlinks.check_url(url, timeout=1) == (None, url)


def test_markdown_bold_wrapper_is_not_part_of_url():
    text = "**[datetime](https://docs.python.org/3/library/datetime.html)**"
    assert [u for _, u in deadlinks.extract_urls(text)] == ["https://docs.python.org/3/library/datetime.html"]


def test_json_output(tmp_path, capsys, monkeypatch):
    import json
    monkeypatch.setattr(deadlinks, "find_dead",
                        lambda *a, **k: ([("a.md", 3, "https://gone.test/x", 404)], []))
    assert deadlinks.main([str(tmp_path), "--json"]) == 1
    assert json.loads(capsys.readouterr().out) == [
        {"file": "a.md", "line": 3, "url": "https://gone.test/x", "status": 404}]


def test_moved_text_output(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(deadlinks, "find_dead",
                        lambda *a, **k: ([], [("a.md", 2, "https://old.test/x", "https://new.test/x")]))
    assert deadlinks.main([str(tmp_path), "--moved"]) == 0
    out = capsys.readouterr().out
    assert "a.md:2: moved https://old.test/x -> https://new.test/x" in out
    assert "1 moved link(s)" in out


def test_moved_json_output(tmp_path, capsys, monkeypatch):
    import json
    monkeypatch.setattr(deadlinks, "find_dead",
                        lambda *a, **k: ([], [("a.md", 2, "https://old.test/x", "https://new.test/x")]))
    assert deadlinks.main([str(tmp_path), "--json", "--moved"]) == 0
    assert json.loads(capsys.readouterr().out) == [
        {"file": "a.md", "line": 2, "url": "https://old.test/x", "status": "moved",
         "final_url": "https://new.test/x"}]



def test_rst_wrapped_link_target_is_joined():
    text = ("See `Configuring MathJax`__.\n\n"
            "   __ https://docs.mathjax.org/en/stable/web/\n"
            "      configuration.html#configuration\n")
    assert deadlinks.extract_urls(text) == [
        (3, "https://docs.mathjax.org/en/stable/web/configuration.html#configuration")]


def test_rst_multi_line_wrapped_target():
    text = ("__ https://a.test/docs/\n"
            "   reference/\n"
            "   guide.html\n")
    assert deadlinks.extract_urls(text) == [(1, "https://a.test/docs/reference/guide.html")]


def test_rst_wrapped_target_drops_angle_bracket_closer():
    text = ("the other flavors `github accepts <https://help.example/en/articles/\n"
            "   closing-issues-using-keywords>`_.\n")
    assert deadlinks.extract_urls(text) == [
        (1, "https://help.example/en/articles/closing-issues-using-keywords")]


def test_indented_line_after_url_is_not_joined():
    text = "Docs at https://docs.test/page\n    indented_code()\n"
    assert deadlinks.extract_urls(text) == [(1, "https://docs.test/page")]


def test_directive_after_url_is_not_joined():
    text = "__ https://a.test/docs/\n.. note:: text\n"
    assert deadlinks.extract_urls(text) == [(1, "https://a.test/docs/")]


class _FakeResponse:
    def __init__(self, status, url):
        self.status = status
        self._url = url

    def geturl(self):
        return self._url

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def test_check_url_sends_browser_user_agent(monkeypatch):
    seen = []

    def fake_urlopen(request, timeout=10):
        seen.append(request.get_header("User-agent"))
        return _FakeResponse(200, "https://x.test/")

    monkeypatch.setattr(deadlinks.urllib.request, "urlopen", fake_urlopen)
    deadlinks.check_url("https://x.test/", retries=0)
    assert seen and seen[0].startswith("Mozilla/5.0 ")
    assert "AppleWebKit" in seen[0]


def test_check_url_retries_transient_5xx(monkeypatch):
    import urllib.error
    calls = []

    def fake_urlopen(request, timeout=10):
        calls.append(request.get_method())
        if len(calls) == 1:
            raise urllib.error.HTTPError("https://x.test/", 503, "err", {}, None)
        return _FakeResponse(200, "https://x.test/")

    monkeypatch.setattr(deadlinks.urllib.request, "urlopen", fake_urlopen)
    sleeps = []
    status, final = deadlinks.check_url("https://x.test/", retries=1, sleeper=sleeps.append)
    assert (status, final) == (200, "https://x.test/")
    assert calls == ["HEAD", "HEAD"]
    assert sleeps == [1.0]


def test_check_url_does_not_retry_permanent_404(monkeypatch):
    import urllib.error
    calls = []

    def fake_urlopen(request, timeout=10):
        calls.append(request.get_method())
        raise urllib.error.HTTPError("https://x.test/", 404, "err", {}, None)

    monkeypatch.setattr(deadlinks.urllib.request, "urlopen", fake_urlopen)
    status, _ = deadlinks.check_url("https://x.test/", retries=2, sleeper=lambda s: None)
    assert status == 404
    assert calls == ["HEAD", "GET"]  # one attempt only: HEAD falls back to GET


def test_check_url_retries_network_error_then_gives_up(monkeypatch):
    import urllib.error
    calls = []

    def fake_urlopen(request, timeout=10):
        calls.append(1)
        raise urllib.error.URLError("unreachable")

    monkeypatch.setattr(deadlinks.urllib.request, "urlopen", fake_urlopen)
    sleeps = []
    status, final = deadlinks.check_url("https://x.test/", retries=2, retry_delay=0.5, sleeper=sleeps.append)
    assert (status, final) == (None, "https://x.test/")
    assert len(calls) == 3 and sleeps == [0.5, 0.5]


def test_retries_cli_option_is_forwarded(tmp_path, capsys, monkeypatch):
    seen = {}

    def fake_check(u, t=10, retries=1):
        seen["retries"] = retries
        return (200, u)

    (tmp_path / "a.md").write_text("https://ok.test/x\n")
    monkeypatch.setattr(deadlinks, "check_url", fake_check)
    assert deadlinks.main([str(tmp_path), "--retries", "3"]) == 0
    assert seen["retries"] == 3


def test_negative_retries_is_rejected():
    with pytest.raises(SystemExit) as excinfo:
        deadlinks.main([".", "--retries", "-1"])
    assert excinfo.value.code == 2


def test_zero_workers_is_rejected():
    with pytest.raises(SystemExit) as excinfo:
        deadlinks.main([".", "--workers", "0"])
    assert excinfo.value.code == 2


def test_nonpositive_timeout_is_rejected():
    with pytest.raises(SystemExit) as excinfo:
        deadlinks.main([".", "--timeout", "0"])
    assert excinfo.value.code == 2


def test_check_url_survives_invalid_ipv6_url():
    status, _ = deadlinks.check_url("http://[::1", timeout=1, retries=0)
    assert status is None


def test_markdown_link_suffix_is_not_part_of_url():
    text = "requires [PEP 440](https://peps.python.org/pep-0440)-compliant versions"
    assert deadlinks.extract_urls(text) == [(1, "https://peps.python.org/pep-0440")]


def test_vcs_install_specifier_is_skipped():
    text = ('poetry add git+https://github.com/org/repo.git@main\n'
            'but see https://github.com/org/docs for details\n')
    assert deadlinks.extract_urls(text) == [(2, "https://github.com/org/docs")]
