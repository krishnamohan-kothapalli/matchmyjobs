from pydantic import BaseModel
from typing import List, Dict, Any, Optional


class AnalysisRequest(BaseModel):
    resume_text: str
    jd_text: str
    email: Optional[str] = None  # User email for database usage tracking


class DensityResult(BaseModel):
    labels: List[str]
    jd_counts: List[int]
    res_counts: List[int]
    explanation: str


class AuditItem(BaseModel):
    status: str
    msg: str


class ScoreBreakdown(BaseModel):
    keyword_overlap:   float
    semantic_match:    float
    keyword_placement: float
    structure:         float
    seniority:         float
    impact:            float
    contact:           float
    penalties:         float


class Suggestion(BaseModel):
    area:     str
    priority: str
    issue:    str
    fix:      str
    impact:   str


class AnalysisResponse(BaseModel):
    score:           float
    seniority_match: str
    recent_hits:     List[str]
    missing:         List[str]
    soft_skills:     List[str]
    density:         DensityResult
    audit:           Dict[str, List[AuditItem]]
    score_breakdown: ScoreBreakdown
    suggestions:     List[Dict[str, Any]]
    jd_parsed:       Dict[str, Any]
