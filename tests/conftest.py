from __future__ import annotations

import gc
import os
from collections.abc import Iterator

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QEvent
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="session")
def qapp() -> Iterator[QApplication]:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    if not isinstance(app, QApplication):
        raise TypeError("Expected QApplication instance for widget tests")

    app.setQuitOnLastWindowClosed(False)
    yield app

    app.closeAllWindows()
    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    app.processEvents()
    gc.collect()


@pytest.fixture(autouse=True)
def _cleanup_qt_state(qapp: QApplication) -> Iterator[None]:
    yield

    qapp.closeAllWindows()
    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    qapp.processEvents()
