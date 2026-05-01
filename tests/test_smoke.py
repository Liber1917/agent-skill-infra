"""Smoke test: verify project structure is importable."""


def test_package_importable():
    import skill_infra

    assert skill_infra.__version__ == "0.3.0"


def test_submodules_importable():
    from skill_infra import quality_check, shared, test_runner, version_aware

    assert shared is not None
    assert quality_check is not None
    assert test_runner is not None
    assert version_aware is not None
