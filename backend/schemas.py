from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel


class AnalyzeRequest(BaseModel):
    resume_text: str
    job_description: str


class SkillGapOut(BaseModel):
    skill: str
    category: Optional[str] = None
    priority: str  # high | medium | low

    class Config:
        from_attributes = True


class ResourceOut(BaseModel):
    rank: int
    title: str
    source: str
    url: str
    level: Optional[str] = None
    skill_addressed: Optional[str] = None
    justification: Optional[str] = None
    score: Optional[float] = None
    description_score: Optional[float] = None   # LLM relevance score 0–10
    description_reason: Optional[str] = None    # LLM reason why this was surfaced

    class Config:
        from_attributes = True


class AnalysisResponse(BaseModel):
    analysis_id: int
    skill_gaps: List[SkillGapOut]
    learning_path: List[ResourceOut]
    created_at: datetime

    class Config:
        from_attributes = True


class AnalysisSummary(BaseModel):
    analysis_id: int
    resume_snippet: str
    job_snippet: str
    skill_gap_count: int
    resource_count: int
    created_at: datetime

    class Config:
        from_attributes = True


class AnalysisListResponse(BaseModel):
    analyses: List[AnalysisSummary]


class ResumeSummary(BaseModel):
    analysis_id: int
    snippet: str  # first 80 chars
    full_text: str
    created_at: datetime

    class Config:
        from_attributes = True


class ResumeListResponse(BaseModel):
    resumes: List[ResumeSummary]
