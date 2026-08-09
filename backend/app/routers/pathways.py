from fastapi import APIRouter

from app.schemas import PathwayOption
from app.services.pathways import load_pathways

router = APIRouter(prefix="/pathways", tags=["pathways"])


@router.get("", response_model=list[PathwayOption])
def list_pathways():
    """Conditions with a modeled care pathway.

    Used by the UI to offer canonical condition names, so a user's entry maps
    cleanly to a pathway instead of relying on free-text alias matching.
    """
    return [
        PathwayOption(
            id=p["id"], name=p["name"], category=p["category"], summary=p["summary"]
        )
        for p in load_pathways()
    ]
