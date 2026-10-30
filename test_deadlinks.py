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


def test_find_dead_reports_only_404_and_410(tmp_path):
    (tmp_path / "doc.md").write_text(
        "ok https://ok.test/a\ngone https://gone.test/b\nold https://old.test/c\n"
        "slow https://down.test/d\nskip https://skip.test/e\n"
    )
    codes = {"https://ok.test/a": 200, "https://gone.test/b": 404,
             "https://old.test/c": 410, "https://down.test/d": None}
    dead = deadlinks.find_dead(
        [str(tmp_path)], ignore="skip.test", checker=lambda u, t: codes.get(u, 200)
    )
    assert [(line, url, status) for _, line, url, status in dead] == [
        (2, "https://gone.test/b", 404), (3, "https://old.test/c", 410)]


def test_each_url_reported_once_at_first_location(tmp_path):
    (tmp_path / "a.md").write_text("https://gone.test/x\n")
    (tmp_path / "b.md").write_text("\nhttps://gone.test/x\n")
    dead = deadlinks.find_dead([str(tmp_path)], checker=lambda u, t: 404)
    assert len(dead) == 1 and dead[0][0].endswith("a.md")


def test_main_exit_code(tmp_path, capsys, monkeypatch):
    (tmp_path / "a.md").write_text("https://gone.test/x\n")
    monkeypatch.setattr(deadlinks, "check_url", lambda u, t=10: 404)
    monkeypatch.setattr(deadlinks, "find_dead",
                        lambda *a, **k: [("a.md", 1, "https://gone.test/x", 404)])
    assert deadlinks.main([str(tmp_path)]) == 1
    assert "1 dead link(s)" in capsys.readouterr().out


def test_check_url_survives_malformed_url():
    assert deadlinks.check_url("https://host:%d%s/path", timeout=1) is None


def test_markdown_bold_wrapper_is_not_part_of_url():
    text = "**[datetime](https://docs.python.org/3/library/datetime.html)**"
    assert [u for _, u in deadlinks.extract_urls(text)] == ["https://docs.python.org/3/library/datetime.html"]


def test_json_output(tmp_path, capsys, monkeypatch):
    import json
    monkeypatch.setattr(deadlinks, "find_dead",
                        lambda *a, **k: [("a.md", 3, "https://gone.test/x", 404)])
    assert deadlinks.main([str(tmp_path), "--json"]) == 1
    assert json.loads(capsys.readouterr().out) == [
        {"file": "a.md", "line": 3, "url": "https://gone.test/x", "status": 404}]
