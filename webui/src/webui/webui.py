"""Reflex expects the app module at `<app_name>.<app_name>` by default.

With `app_name="webui"` this means it imports `webui.webui`.
We keep the actual app definition in `webui.app` and re-export it here.
"""

from webui.app import app  # noqa: F401


