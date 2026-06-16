
from pydantic import BaseModel

from app.schemas.projects import ProjectRead


class DemoSeedCounts(BaseModel):
    thesis_canvas: int
    thesis_evolution_events: int
    wedge_options: int
    validation_missions: int
    validation_interpretations: int
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
