def test_deprecated_barrel_reexports():
    from app.models import schemas

    assert schemas.TravelPreference is not None
    assert schemas.RecommendationRequest is not None
