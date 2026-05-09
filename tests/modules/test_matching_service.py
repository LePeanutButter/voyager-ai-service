import pytest

from app.ml.learning_store import MatchingLearningStore
from app.modules.common.schemas.base import Location
from app.modules.common.schemas.enums import TravelPreference
from app.modules.matching.schemas import TravelerMatchRequest
from app.modules.matching.service import MatchingService


class _FakeModelManager:
    def get_model(self, _name: str):
        return None


@pytest.fixture
def svc():
    service = MatchingService(_FakeModelManager(), MatchingLearningStore())
    service.ingest_profiles(
        [
            {"user_id": "user1", "name": "Ana", "location": "Barcelona", "preferences": ["cultural"]},
            {"user_id": "user2", "name": "Luis", "location": "Barcelona", "preferences": ["cultural", "foodie"]},
            {"user_id": "user3", "name": "Marta", "location": "Madrid", "preferences": ["adventure"]},
        ]
    )
    return service


def test_find_travel_partners_happy_path(svc: MatchingService):
    req = TravelerMatchRequest(
        user_id="user1",
        location=Location(latitude=41.39, longitude=2.15, city="Barcelona"),
        preferences=[TravelPreference.CULTURAL],
        max_matches=2,
    )
    out = svc.find_travel_partners(req)
    assert out.user_id == "user1"
    assert out.total_matches <= 2


@pytest.mark.asyncio
async def test_calculate_compatibility_happy_path(svc: MatchingService):
    out = await svc.calculate_compatibility("user1", "user2")
    assert out is not None
    assert out["user_id"] == "user1"


def test_connection_flow(svc: MatchingService):
    c = svc.initiate_connection("user1", "user2", message="hola")
    assert c["status"] == "pending"
    updated = svc.respond_to_connection(c["connection_id"], "accepted", message="vamos")
    assert updated is not None
    assert updated["status"] == "accepted"

