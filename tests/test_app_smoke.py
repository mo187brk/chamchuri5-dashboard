"""Start the real app headlessly. Skipped automatically when Streamlit is not installed."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(importlib.util.find_spec("streamlit") and importlib.util.find_spec("plotly"),
                     "streamlit and plotly are not installed")
class AppSmoke(unittest.TestCase):
    def test_first_page_renders_without_exception(self):
        from streamlit.testing.v1 import AppTest

        app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=180).run()
        self.assertFalse(app.exception, [e.value for e in app.exception])


if __name__ == "__main__":
    unittest.main()
