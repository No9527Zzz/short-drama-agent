from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

SourceType = Literal["complete_script", "novel", "idea"]


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=2000)
    source_type: SourceType = "idea"


class ProjectSummary(BaseModel):
    id: str
    name: str
    description: str
    source_type: SourceType
    target_episodes: int
    episode_duration_seconds: int
    aspect_ratio: str
    width: int
    height: int
    fps: int
    status: str
    created_at: str
    updated_at: str
