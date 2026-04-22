"""Smoke tests — import が通るかだけ確認."""

import winb


def test_version():
    assert winb.__version__ == "0.1.0"


def test_imports():
    from winb import data, evaluation, features, models, pipeline, scraper  # noqa: F401
