def test_config_withdraw_updates(monkeypatch):
    captured = {}
    # Capture env updates instead of writing files
    import provider.main as m
    from provider.main import config_withdraw
    def fake_write(path, updates):
        captured.update(updates)
    monkeypatch.setattr(m, "_write_env_vars", fake_write)
    # Call function directly to validate logic without Typer parsing
    config_withdraw(enable=True, interval=900, min_wei=1000, dev=True)
    assert captured["GOLEM_PROVIDER_STREAM_WITHDRAW_ENABLED"] == "true"
    assert captured["GOLEM_PROVIDER_STREAM_WITHDRAW_INTERVAL_SECONDS"] == 900
    assert captured["GOLEM_PROVIDER_STREAM_MIN_WITHDRAW_WEI"] == 1000


def test_config_monitor_updates(monkeypatch):
    captured = {}
    import provider.main as m
    from provider.main import config_monitor
    def fake_write(path, updates):
        captured.update(updates)
    monkeypatch.setattr(m, "_write_env_vars", fake_write)
    # Call function directly
    config_monitor(enable=True, interval=30, min_remaining=3600, dev=False)
    assert captured["GOLEM_PROVIDER_STREAM_MONITOR_ENABLED"] == "true"
    assert captured["GOLEM_PROVIDER_STREAM_MONITOR_INTERVAL_SECONDS"] == 30
    assert captured["GOLEM_PROVIDER_STREAM_MIN_REMAINING_SECONDS"] == 3600
