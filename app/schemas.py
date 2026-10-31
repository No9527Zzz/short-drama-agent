from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

SourceType = Literal["complete_script", "novel", "idea"]
PlanStatus = Literal["draft", "review", "approved"]


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


class SourceCreate(BaseModel):
    title: str = Field(default="", max_length=200)
    content: str = Field(min_length=1, max_length=2_000_000)
    source_type: SourceType | None = None


class SourceSummary(BaseModel):
    id: str
    project_id: str
    source_type: SourceType
    title: str
    content: str
    version: int
    is_current: bool
    created_at: str


class EpisodePlan(BaseModel):
    id: str
    project_id: str
    episode_number: int
    title: str
    logline: str
    plot_summary: str
    key_conflict: str
    ending_hook: str
    status: PlanStatus
    plan_version: int
    is_current: bool
    created_at: str
    updated_at: str


class EpisodePlanUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    logline: str = Field(default="", max_length=1000)
    plot_summary: str = Field(default="", max_length=4000)
    key_conflict: str = Field(default="", max_length=1000)
    ending_hook: str = Field(default="", max_length=1000)
    status: PlanStatus = "draft"


class PlanningSummary(BaseModel):
    project_id: str
    plan_version: int
    episode_count: int
    source_version: int
    status: str

