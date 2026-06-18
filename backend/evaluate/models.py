from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class EntitySpec(BaseModel):
    type: str
    value: str


class EdgeSpec(BaseModel):
    source_value: str
    target_value: str
    label: str = ""


class EvalTask(BaseModel):
    id: str
    question: str
    dataset_path: str
    seed_entities: List[EntitySpec]
    ground_truth_entities: List[EntitySpec]
    ground_truth_edges: List[EdgeSpec] = []
    ground_truth_text: Optional[str] = None


class EvalResult(BaseModel):
    task_id: str
    success: bool
    final_summary: str
    step_count: int = 0
    token_count: int = 0
    cost: float = 0.0
    duration: float = 0.0
    precision: float = 0.0
    recall: float = 0.0
    f1_score: float = 0.0
    semantic_score: Optional[float] = None
    judge_reasoning: Optional[str] = None
