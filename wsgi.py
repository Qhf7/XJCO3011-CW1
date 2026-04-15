"""
PythonAnywhere ASGI entry point.

In PythonAnywhere Web tab:
  - Framework: Manual configuration
  - Python version: 3.12
  - WSGI config file: /home/<username>/nutrition-api/wsgi.py

Then in the WSGI file add:
    import sys
    sys.path.insert(0, '/home/<username>/nutrition-api')
    from wsgi import application
"""

import os
os.environ.setdefault("DATABASE_URL", "sqlite:///./nutrition_demo.db")

from app.main import app as application  # noqa: F401  (ASGI app)
