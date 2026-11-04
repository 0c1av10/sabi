import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import yummy_quote_driver as drv

DUMPSYS = """Location Service State:
  last location=Location[gps 10.4806,-66.9036 hAcc=5.0]
  passive: Location[network 40.7128,-74.0060 et=...]
"""

def test_parse_last_gps_picks_last_fix():
    lat, lon = drv.parse_last_gps(DUMPSYS)
    assert (lat, lon) == (40.7128, -74.0060)

def test_parse_last_gps_none_on_garbage():
    assert drv.parse_last_gps("no locations here") is None

def test_in_venezuela_bbox():
    assert drv.in_venezuela((10.48, -66.90)) is True      # Caracas
    assert drv.in_venezuela((10.19, -64.68)) is True      # Lecheria
    assert drv.in_venezuela((40.71, -74.00)) is False     # NYC
    assert drv.in_venezuela((-33.45, -70.66)) is False    # Santiago
    assert drv.in_venezuela(None) is None

def test_service_overlay_detection():
    assert drv.service_overlay_shown(
        [{"text": "Sorry!"}, {"text": "No service available in this area."}])
    assert not drv.service_overlay_shown(
        [{"text": "Where are we going?"}, {"text": "Yummy Moto $2.10"}])
    assert not drv.service_overlay_shown([])


def test_gps_report_distinguishes_stale_and_disabled():
    fresh = """gps provider:
    enabled
    last location=Location[gps 10.4806,-66.9036 et=+2m30s]"""
    out = drv.gps_report(fresh)
    assert "fix=yes" in out and "fix_age=<5m" in out and "gps_enabled=True" in out
    stale = """gps provider:
    disabled
    last location=Location[gps 10.4806,-66.9036 et=+3d4h10m5s]"""
    out = drv.gps_report(stale)
    assert "fix=yes" in out and "fix_age=>=76h" in out and "gps_enabled=False" in out
    assert drv.gps_report("") == "unavailable"
    assert "fix=no" in drv.gps_report("gps provider:\n  enabled\n  no last location")
