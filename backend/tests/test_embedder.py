import math

import pytest

from app.enrichment.embedder import embed


@pytest.mark.live
async def test_embedding_dimensions_and_normalization() -> None:
    values = await embed("test article summary")

    assert len(values) == 384
    assert all(isinstance(value, float) for value in values)
    assert all(-1.0 <= value <= 1.0 for value in values)
    assert math.isclose(
        math.sqrt(sum(value * value for value in values)),
        1.0,
        rel_tol=1e-5,
    )
