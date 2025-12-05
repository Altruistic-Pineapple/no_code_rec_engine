from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from backend.database import get_db
from backend import models
from pydantic import BaseModel
from typing import Optional

router = APIRouter()

class BusinessRulesRequest(BaseModel):
    """Business rules for filtering and re-ranking recommendations"""
    max_diversity: Optional[float] = 1.0  # 0-1, how diverse recommendations should be
    min_content_score: Optional[float] = 0.0  # Minimum score threshold
    max_results: Optional[int] = 10  # Max number of results
    exclude_tags: Optional[list] = []  # Tags to exclude
    include_tags: Optional[list] = []  # Tags to only include (if specified)
    boost_tags: Optional[list] = []  # Tags to boost in scoring
    max_from_same_tag: Optional[int] = 3  # Max recommendations from same tag
    random_sample: Optional[bool] = False  # Add randomness to recommendations
    pinned_content_ids: Optional[list] = []  # Content IDs to pin at top of results


class BusinessRulesResponse(BaseModel):
    mix_id: str
    rules: dict
    
    class Config:
        from_attributes = True


@router.post("/set-rules", response_model=BusinessRulesResponse)
def set_business_rules(mix_id: str, rules: dict = Body(...), db: Session = Depends(get_db)):
    """Store business rules for a mix"""
    
    print(f"DEBUG: Received rules for mix {mix_id}: {rules}")
    
    # Check if mix exists
    mix = db.query(models.Mix).filter(models.Mix.id == mix_id).first()
    if not mix:
        raise HTTPException(status_code=404, detail="Mix not found")
    
    # Store rules directly as dict
    rules_dict = rules
    print(f"DEBUG: Storing rules_dict: {rules_dict}")
    
    # Check if rules already exist
    existing_rules = db.query(models.BusinessRules).filter(models.BusinessRules.mix_id == mix_id).first()
    
    if existing_rules:
        # Update existing rules
        existing_rules.rules = rules_dict
        db.commit()
        db.refresh(existing_rules)
        return existing_rules
    else:
        # Create new rules
        new_rules = models.BusinessRules(mix_id=mix_id, rules=rules_dict)
        db.add(new_rules)
        db.commit()
        db.refresh(new_rules)
        return new_rules


@router.get("/get-rules", response_model=BusinessRulesResponse)
def get_business_rules(mix_id: str, db: Session = Depends(get_db)):
    """Retrieve business rules for a mix"""
    
    rules = db.query(models.BusinessRules).filter(models.BusinessRules.mix_id == mix_id).first()
    print(f"DEBUG: get-rules for mix {mix_id}: rules={rules}")
    
    if not rules:
        # Return default empty rules
        print(f"DEBUG: No rules found, returning defaults")
        return {
            "mix_id": mix_id,
            "rules": {
                "max_diversity": 1.0,
                "min_content_score": 0.0,
                "max_results": 10,
                "exclude_tags": [],
                "include_tags": [],
                "boost_tags": [],
                "max_from_same_tag": 3,
                "random_sample": False,
                "pinned_content_ids": []
            }
        }
    
    print(f"DEBUG: Returning rules.rules = {rules.rules}")
    return rules


@router.delete("/delete-rules")
def delete_business_rules(mix_id: str, db: Session = Depends(get_db)):
    """Delete business rules for a mix"""
    
    rules = db.query(models.BusinessRules).filter(models.BusinessRules.mix_id == mix_id).first()
    
    if not rules:
        raise HTTPException(status_code=404, detail="Rules not found")
    
    db.delete(rules)
    db.commit()
    
    return {"message": "Rules deleted successfully"}
