"""테스트 공통 fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

from rebar_audit.fixtures import generate_all


@pytest.fixture(scope="session")
def sample_paths(tmp_path_factory) -> dict[str, Path]:
    """테스트 세션 내내 재사용할 더미 샘플 디렉토리."""
    out_dir = tmp_path_factory.mktemp("samples")
    return generate_all(out_dir)
