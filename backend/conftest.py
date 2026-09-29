"""Pytest defaults for the backend suite.

auth.py refuses to import without JWT_SECRET_KEY (correct for production).
Tests use a throwaway value unless the developer already set one.
"""
import os

os.environ.setdefault("JWT_SECRET_KEY", "xelora-test-only-secret-not-for-production")
