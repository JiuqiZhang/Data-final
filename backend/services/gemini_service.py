import json
import os
import re
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
_MODEL = "gemini-2.5-flash"
_CONFIG = types.GenerateContentConfig(response_mime_type="application/json")


def _parse_json(text: str):
    """Parse JSON from model response, stripping markdown code fences if present."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return json.loads(text.strip())


async def extract_skill_gaps(resume_text: str, job_description: str) -> dict:
    """
    Returns {resume_skills, jd_skills, skill_gaps: [{skill, category, priority}]}
    """
    prompt = f"""You are a professional technical recruiter and skills assessor.

Your tasks:
1. Extract all technical skills mentioned in the resume as a flat list.
2. Extract all required and preferred technical skills from the job description.
3. Identify the SKILL GAPS: skills in the job description that are absent or
   insufficiently demonstrated in the resume.
4. For each skill gap, assign a priority:
   - "high"   → listed as required or mentioned multiple times in the JD
   - "medium" → listed as preferred or mentioned once
   - "low"    → implied by context but not stated explicitly
5. For each skill gap, assign a category from:
   ["Programming Language", "ML/AI Framework", "Big Data", "Statistics",
    "Database", "Data Visualization", "Cloud/DevOps", "Soft Skill", "Other"]

Return a JSON object with this exact schema:
{{
  "resume_skills": ["string"],
  "jd_skills": ["string"],
  "skill_gaps": [
    {{
      "skill": "string",
      "category": "string",
      "priority": "high | medium | low"
    }}
  ]
}}

RESUME:
{resume_text}

JOB DESCRIPTION:
{job_description}"""

    response = await _client.aio.models.generate_content(
        model=_MODEL, contents=prompt, config=_CONFIG
    )
    return _parse_json(response.text)


async def evaluate_descriptions(skill_gaps: list[dict], resources: list[dict]) -> list[dict]:
    """
    For each resource {index, title, description, skill_addressed},
    evaluate whether the video description matches the skill gap.
    Returns [{resource_index, relevance_score (0–10), reason}].
    Only YouTube resources (with real descriptions) should be passed in.
    """
    if not resources:
        return []

    prompt = f"""You are evaluating educational videos for relevance to specific skill gaps in a technology/data career context.

For each video below, evaluate: does the title and description demonstrate that this video
genuinely teaches the listed skill_addressed for a software/data professional?

Return a JSON array in the same order as the input:
[
  {{
    "resource_index": 0,
    "relevance_score": 7,
    "reason": "one sentence explaining the match or mismatch"
  }}
]

Rules:
- relevance_score is 0–10 (0 = completely off-topic, 10 = perfect match)
- reason must be specific to the skill name, not generic
- Score 0–2 if the video is from an entirely unrelated domain (e.g., cooking, fitness,
  video editing software, lifestyle, or corporate law/auditing) even if the skill keyword
  appears in the title. The skill must be taught in a tech, software, or professional
  development context relevant to the skill gaps provided.
- For soft skills (communication, collaboration, responsibility, etc.), the content must
  be professional/workplace focused — not lifestyle, cooking, video production, etc.

SKILL GAPS (for context):
{json.dumps(skill_gaps, indent=2)}

VIDEOS:
{json.dumps(resources, indent=2)}"""

    response = await _client.aio.models.generate_content(
        model=_MODEL, contents=prompt, config=_CONFIG
    )
    return _parse_json(response.text)


async def tag_resources(skill_gaps: list[dict], resources: list[dict]) -> list[dict]:
    """
    Given skill gaps and a list of resources with {index, title, source, skill_addressed},
    returns [{resource_index, level, justification}] in input order.
    """
    if not resources:
        return []

    prompt = f"""You are a curriculum designer classifying educational resources by difficulty level.

Use these exact definitions — do not default to "intermediate" when unsure:
- "beginner": assumes NO prior knowledge of the topic. Covers what it is and why it matters.
  Typical signals: introduction, overview, crash course, from scratch, 101, for beginners.
- "intermediate": assumes the viewer knows the basics and wants to apply them.
  Typical signals: hands-on project, practical, building something real, in-depth walkthrough.
- "advanced": assumes strong background. Covers architecture, optimization, production use,
  edge cases, or research.
  Typical signals: at scale, production, fine-tuning, internals, best practices, deep dive.

For each resource below, provide:
1. "level": one of exactly "beginner", "intermediate", or "advanced" — lowercase, no other values.
2. "justification": a 1-sentence explanation of why this resource helps address
   the listed skill gap. Be specific to the skill name.

Return a JSON array matching the input order:
[
  {{
    "resource_index": 0,
    "level": "beginner | intermediate | advanced",
    "justification": "string"
  }}
]

SKILL GAPS (for context):
{json.dumps(skill_gaps, indent=2)}

RESOURCES:
{json.dumps(resources, indent=2)}"""

    response = await _client.aio.models.generate_content(
        model=_MODEL, contents=prompt, config=_CONFIG
    )
    return _parse_json(response.text)
