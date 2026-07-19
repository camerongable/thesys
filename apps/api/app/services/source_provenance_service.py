"""Compatibility wrapper for evidence source provenance helpers.

Sprint 59 moves feature-owned evidence logic under `app.features.evidence`.
Keep this module so existing imports continue to work during the package
refactor.
"""

from app.features.evidence.source_provenance import *  # noqa: F403
