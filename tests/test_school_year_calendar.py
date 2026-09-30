"""Der Kalender des ganzen Schuljahres, nicht nur die nächsten drei Wochen."""
from datetime import date

import pytest

from journal.integrations import schuljahr_fenster, sync_school_year


@pytest.mark.parametrize('tag,beginn,ende', [
    (date(2026, 9, 30), date(2026, 8, 1), date(2027, 7, 31)),
    (date(2027, 3, 15), date(2026, 8, 1), date(2027, 7, 31)),
    (date(2026, 8, 1), date(2026, 8, 1), date(2027, 7, 31)),
    (date(2026, 7, 31), date(2025, 8, 1), date(2026, 7, 31)),
])
def test_fenster_umfasst_das_ganze_schuljahr(tag, beginn, ende):
    assert schuljahr_fenster(tag) == (beginn, ende)


def test_ladelauf_deckt_august_bis_juli(app, monkeypatch):
    gerufen = {}

    def merken(start, days):
        gerufen.update(start=start, days=days)
        return '1 Kalender aktualisiert'

    monkeypatch.setattr('journal.integrations.sync_calendar', merken)
    with app.app_context():
        assert sync_school_year(date(2026, 9, 30)) == '1 Kalender aktualisiert'
    assert gerufen['start'] == date(2026, 8, 1)
    assert gerufen['days'] == 365, 'vom 1. August bis einschließlich 31. Juli'


def test_schaltjahr_wird_mitgezaehlt(app, monkeypatch):
    gerufen = {}
    monkeypatch.setattr('journal.integrations.sync_calendar',
                        lambda start, days: gerufen.update(days=days) or 'ok')
    with app.app_context():
        sync_school_year(date(2027, 9, 1))
    assert gerufen['days'] == 366, 'Schuljahr 2027/28 enthält den 29. Februar 2028'
