from datetime import date, timedelta
from pathlib import Path

from imagery import album_dates
from security import (MIN_ADMIN_PASSWORD_LENGTH, RATE_LIMITS, admin_password, allow, check_password, log_incident,
                      rate_check)


def test_rate_limit_blocks_then_releases():
    state = {}
    limit, window = RATE_LIMITS["analysis"]
    for i in range(limit):
        assert allow("analysis", state, now=1000 + i)[0]
    ok, wait = allow("analysis", state, now=1000 + limit)
    assert not ok and 0 < wait <= window
    assert allow("analysis", state, now=1000 + window + 1)[0]
    assert rate_check([], 0, 1, 10) == (True, 0)


def test_admin_password_rules():
    assert admin_password(lambda k: "") is None
    assert admin_password(lambda k: "court") is None
    good = "x" * MIN_ADMIN_PASSWORD_LENGTH
    assert admin_password(lambda k: good) == good
    assert admin_password(lambda k: (_ for _ in ()).throw(KeyError(k))) is None
    assert check_password(good, good) and not check_password("x", good) and not check_password(None, good)


def test_incident_reference_hides_details(caplog):
    ref = log_incident("test", RuntimeError("clé secrète /home/app/key.json"))
    assert len(ref) == 8 and "secrète" not in ref
    assert ref in caplog.text


def test_streamlit_config_hides_errors_and_dev_tools():
    cfg = (Path(__file__).resolve().parent.parent / ".streamlit" / "config.toml").read_text()
    assert 'showErrorDetails = "none"' in cfg
    assert 'toolbarMode = "viewer"' in cfg
    assert "enableXsrfProtection = true" in cfg


def test_no_secret_files_tracked():
    root = Path(__file__).resolve().parent.parent
    assert not (root / ".streamlit" / "secrets.toml").exists() or ".streamlit/secrets.toml" in (root / ".gitignore").read_text()
    for p in root.rglob("*.json"):
        if ".git" in p.parts:
            continue
        assert '"private_key"' not in p.read_text(errors="ignore"), p


def test_album_dates_spread():
    days = [date(2026, 1, 1) + timedelta(days=5 * i) for i in range(40)]
    picked = album_dates(days, 8)
    assert len(picked) == 8 and picked[0] == days[0] and picked[-1] == days[-1]
    assert picked == sorted(picked)
    assert album_dates(days[:3], 8) == days[:3]
