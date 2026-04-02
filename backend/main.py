from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import engine, Base
from routers import analyze, results, parse

# Create all tables on startup
Base.metadata.create_all(bind=engine)

app = FastAPI(title="E-Learning Skill Architect API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(analyze.router)
app.include_router(results.router)
app.include_router(parse.router)


@app.get("/health")
def health():
    return {"status": "ok"}
