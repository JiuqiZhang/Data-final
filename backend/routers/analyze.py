import asyncio
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import Analysis, SkillGap, Resource
from schemas import AnalyzeRequest, AnalysisResponse, SkillGapOut, ResourceOut
from services import gemini_service, youtube_service, oer_service, ranker

router = APIRouter()


@router.post("/analyze", response_model=AnalysisResponse)
async def analyze(request: AnalyzeRequest, db: Session = Depends(get_db)):
    if not request.resume_text.strip():
        raise HTTPException(status_code=422, detail="Resume text cannot be empty.")
    if not request.job_description.strip():
        raise HTTPException(status_code=422, detail="Job description cannot be empty.")

    # Step 1: Gemini skill gap extraction
    try:
        extraction = await gemini_service.extract_skill_gaps(
            request.resume_text, request.job_description
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Skill extraction failed: {str(e)}")

    skill_gaps = extraction.get("skill_gaps", [])
    if not skill_gaps:
        raise HTTPException(
            status_code=200,
            detail="No skill gaps detected — your resume already covers the job requirements!",
        )

    # Step 2: Fetch resources for each skill gap in parallel
    async def fetch_for_gap(gap: dict) -> list[dict]:
        skill = gap["skill"]
        yt_task = youtube_service.search_youtube(skill, category=gap.get("category", ""))
        oer_task = oer_service.search_oer(skill)
        yt_results, oer_results = await asyncio.gather(yt_task, oer_task, return_exceptions=True)

        resources = []
        if isinstance(yt_results, list):
            for r in yt_results:
                r["skill_addressed"] = skill
                resources.append(r)
        if isinstance(oer_results, list):
            for r in oer_results:
                r["skill_addressed"] = skill
                resources.append(r)
        return resources

    fetch_tasks = [fetch_for_gap(g) for g in skill_gaps]
    fetched_lists = await asyncio.gather(*fetch_tasks, return_exceptions=True)

    all_resources: list[dict] = []
    for lst in fetched_lists:
        if isinstance(lst, list):
            all_resources.extend(lst)

    # Step 3: Rank and tag resources
    try:
        learning_path = await ranker.build_learning_path(all_resources, skill_gaps)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ranking failed: {str(e)}")

    # Step 4: Persist to SQLite
    db_analysis = Analysis(
        resume_text=request.resume_text,
        job_description=request.job_description,
    )
    db.add(db_analysis)
    db.flush()  # get db_analysis.id before committing

    for gap in skill_gaps:
        db.add(SkillGap(
            analysis_id=db_analysis.id,
            skill=gap["skill"],
            category=gap.get("category"),
            priority=gap.get("priority", "medium"),
        ))

    for r in learning_path:
        db.add(Resource(
            analysis_id=db_analysis.id,
            rank=r["rank"],
            title=r["title"],
            source=r["source"],
            url=r["url"],
            level=r.get("level"),
            skill_addressed=r.get("skill_addressed"),
            justification=r.get("justification"),
            raw_score=r.get("raw_score"),
            description_score=r.get("description_score"),
            description_reason=r.get("description_reason"),
        ))

    db.commit()
    db.refresh(db_analysis)

    return AnalysisResponse(
        analysis_id=db_analysis.id,
        skill_gaps=[
            SkillGapOut(skill=g["skill"], category=g.get("category"), priority=g.get("priority", "medium"))
            for g in skill_gaps
        ],
        learning_path=[
            ResourceOut(
                rank=r["rank"],
                title=r["title"],
                source=r["source"],
                url=r["url"],
                level=r.get("level"),
                skill_addressed=r.get("skill_addressed"),
                justification=r.get("justification"),
                score=r.get("raw_score"),
                description_score=r.get("description_score"),
                description_reason=r.get("description_reason"),
            )
            for r in learning_path
        ],
        created_at=db_analysis.created_at,
    )
