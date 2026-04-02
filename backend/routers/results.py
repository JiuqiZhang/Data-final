from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import Analysis
from schemas import AnalysisListResponse, AnalysisSummary, AnalysisResponse, SkillGapOut, ResourceOut, ResumeListResponse, ResumeSummary

router = APIRouter()


@router.get("/resumes", response_model=ResumeListResponse)
def list_resumes(db: Session = Depends(get_db)):
    """Return one entry per unique resume text (deduplicated), most recent first."""
    analyses = db.query(Analysis).order_by(Analysis.created_at.desc()).all()
    seen = set()
    resumes = []
    for a in analyses:
        key = a.resume_text.strip()
        if key in seen:
            continue
        seen.add(key)
        resumes.append(ResumeSummary(
            analysis_id=a.id,
            snippet=a.resume_text[:80].replace("\n", " ").strip(),
            full_text=a.resume_text,
            created_at=a.created_at,
        ))
    return ResumeListResponse(resumes=resumes)


@router.get("/results", response_model=AnalysisListResponse)
def list_results(db: Session = Depends(get_db)):
    analyses = db.query(Analysis).order_by(Analysis.created_at.desc()).all()
    summaries = [
        AnalysisSummary(
            analysis_id=a.id,
            resume_snippet=a.resume_text[:120],
            job_snippet=a.job_description[:120],
            skill_gap_count=len(a.skill_gaps),
            resource_count=len(a.resources),
            created_at=a.created_at,
        )
        for a in analyses
    ]
    return AnalysisListResponse(analyses=summaries)


@router.get("/results/{analysis_id}", response_model=AnalysisResponse)
def get_result(analysis_id: int, db: Session = Depends(get_db)):
    a = db.query(Analysis).filter(Analysis.id == analysis_id).first()
    if not a:
        raise HTTPException(status_code=404, detail="Analysis not found.")

    return AnalysisResponse(
        analysis_id=a.id,
        skill_gaps=[
            SkillGapOut(skill=g.skill, category=g.category, priority=g.priority)
            for g in a.skill_gaps
        ],
        learning_path=[
            ResourceOut(
                rank=r.rank,
                title=r.title,
                source=r.source,
                url=r.url,
                level=r.level,
                skill_addressed=r.skill_addressed,
                justification=r.justification,
                score=r.raw_score,
            )
            for r in sorted(a.resources, key=lambda x: x.rank)
        ],
        created_at=a.created_at,
    )
