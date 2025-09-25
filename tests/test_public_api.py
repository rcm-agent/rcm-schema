"""Smoke tests for the public import surface of rcm_schema."""

import importlib


def test_top_level_imports_available():
    module = importlib.import_module("rcm_schema")

    # Legacy models used by existing services
    assert hasattr(module, "PortalType"), "PortalType should be exported for legacy services"
    assert hasattr(module, "RcmState"), "RcmState should be exported for legacy services"

    # V8 workflow models for the new micro state pipeline
    assert hasattr(module, "UserWorkflow"), "UserWorkflow should be exported for V8 services"
    assert hasattr(module, "MicroState"), "MicroState should be exported for V8 services"

    # Both declarative bases should be discoverable for migration scripts
    assert hasattr(module, "LegacyBase")
    assert hasattr(module, "V8Base")
