import sys

from jmoona import cli


def test_main_handles_clear_history(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["jmoona", "--clear-history"])

    called = {"clear_history": False}

    def fake_clear_history():
        called["clear_history"] = True

    monkeypatch.setattr("jmoona.storage.clear_history", fake_clear_history)

    cli.main()

    out = capsys.readouterr().out
    assert called["clear_history"] is True
    assert "Historique" in out


def test_main_handles_top_rated(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["jmoona", "--top-rated"])

    captured = {}

    monkeypatch.setattr("jmoona.tmdb.tmdb_client.top_rated", lambda: [{"id": 1}])
    monkeypatch.setattr("jmoona.storage.load_config", lambda: {"use_fzf": False})

    def fake_handle_list(items, title, args, config):
        captured["items"] = items
        captured["title"] = title
        captured["config"] = config

    monkeypatch.setattr("jmoona.app.handle_list", fake_handle_list)

    cli.main()

    assert captured["items"] == [{"id": 1}]
    assert captured["title"] == "Mieux notés"
    assert captured["config"] == {"use_fzf": False}
