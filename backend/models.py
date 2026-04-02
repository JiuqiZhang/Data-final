from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from database import Base


class Analysis(Base):
    __tablename__ = "analyses"

    id = Column(Integer, primary_key=True, index=True)
    resume_text = Column(Text, nullable=False)
    job_description = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    skill_gaps = relationship("SkillGap", back_populates="analysis", cascade="all, delete-orphan")
    resources = relationship("Resource", back_populates="analysis", cascade="all, delete-orphan")


class SkillGap(Base):
    __tablename__ = "skill_gaps"

    id = Column(Integer, primary_key=True, index=True)
    analysis_id = Column(Integer, ForeignKey("analyses.id"), nullable=False)
    skill = Column(String, nullable=False)
    category = Column(String)
    priority = Column(String)  # high | medium | low

    analysis = relationship("Analysis", back_populates="skill_gaps")


class Resource(Base):
    __tablename__ = "resources"

    id = Column(Integer, primary_key=True, index=True)
    analysis_id = Column(Integer, ForeignKey("analyses.id"), nullable=False)
    rank = Column(Integer, nullable=False)
    title = Column(String, nullable=False)
    source = Column(String, nullable=False)  # YouTube | OER Commons
    url = Column(String, nullable=False)
    level = Column(String)  # beginner | intermediate | advanced
    skill_addressed = Column(String)
    justification = Column(Text)
    raw_score = Column(Float)

    analysis = relationship("Analysis", back_populates="resources")
