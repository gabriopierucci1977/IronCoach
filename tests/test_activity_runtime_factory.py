"""
Test Activity Runtime Factory.
"""

from backend.main import (
    create_activity_runtime,
)


def test_activity_runtime_factory_exists():

    runtime = create_activity_runtime(
        None,
    )

    assert runtime is not None