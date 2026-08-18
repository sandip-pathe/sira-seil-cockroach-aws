"""FastAPI control plane for SIRA + SEIL.

Import the application explicitly from :mod:`sira_api.main`.  Keeping package
initialization side-effect free lets lifecycle and migration tooling load API
configuration without constructing provider clients or the ASGI application.
"""
