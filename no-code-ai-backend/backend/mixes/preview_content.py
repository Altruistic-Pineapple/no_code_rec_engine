from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import MixContent

router = APIRouter()


@router.get("/preview")
async def preview_mapped_content(mix_id: str, db: Session = Depends(get_db)):
    """Return a small preview (up to 5 rows) of MixContent stored in the DB.

    This reads the canonical `mix_contents` table rather than trying to
    load a CSV + mapping from disk.
    """
    contents = (
        db.query(MixContent)
        .filter(MixContent.mix_id == mix_id)
        .limit(5)
        .all()
    )

    if not contents:
        raise HTTPException(status_code=404, detail="No content found for mix")

    preview_rows = []
    for c in contents:
        preview_rows.append({
            "id": c.id,
            "title": c.title,
            "description": c.description,
            "image_url": c.image_url,
            "content_id": c.content_id,
            "tags": c.tags,
        })

    return {"preview": preview_rows}

