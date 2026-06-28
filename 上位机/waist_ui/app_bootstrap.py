# coding: utf-8
"""
Qt application bootstrap helpers.

This module provides a single safe entry for ensuring that a QApplication
exists before any widget class or Fluent UI component is imported.
"""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication


def ensure_qapplication(argv=None) -> QApplication:
    """Return the existing QApplication or create one once."""
    app = QApplication.instance()
    if app is not None:
        return app

    if argv is None:
        argv = sys.argv

    return QApplication(argv)
