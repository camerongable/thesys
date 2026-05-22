
from pydantic import BaseModel

from app.schemas.projects import ProjectRead


class DemoSeedCounts(BaseModel):
    evidence_sources: int
    artifacts: int
    competitors: int
    assumptions: int
    risks: int
    experiments: int
    experiment_results: int
    decisions: int
    ai_runs: int


class DemoSeedRead(BaseModel):
    project: ProjectRead
    created: bool
    counts: DemoSeedCounts
    next_url: str
    message: str
