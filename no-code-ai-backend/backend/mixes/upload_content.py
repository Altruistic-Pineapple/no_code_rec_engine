from fastapi import APIRouter, UploadFile, File, Form, HTTPException
import os

router = APIRouter()


@router.post("/upload-content")
async def upload_content(mix_id: str = Form(...), file: UploadFile = File(...)):
    """Save uploaded CSV to the `uploads/` folder as `{mix_id}.csv`.

    Mapping from user columns to internal fields is applied later by
    `/mixes/map-fields`, which will populate the DB. This keeps upload and
    mapping responsibilities separate and avoids inserting rows with
    incorrect column names into the DB.
    """
    uploads_dir = "uploads"
    os.makedirs(uploads_dir, exist_ok=True)
    target_path = os.path.join(uploads_dir, f"{mix_id}.csv")

    try:
        content = await file.read()
        # write the uploaded bytes directly to the uploads directory
        with open(target_path, "wb") as f:
            f.write(content)

        # report the file size to the client
        return {"message": "File saved", "path": target_path, "size_bytes": len(content)}

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
