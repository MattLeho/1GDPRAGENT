"""API package for the intelligence service.

Routers are imported explicitly by :mod:`main`. Keeping package import lazy
prevents an unrelated optional service dependency from blocking a bounded API.
"""
