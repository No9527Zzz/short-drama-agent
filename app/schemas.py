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



class CharacterAsset(BaseModel):
    id: str
    project_id: str
    name: str
    description: str
    role_type: str
    voice_name: str
    reference_image_path: str
    version: int
    is_current: bool
    created_at: str
    updated_at: str


class LocationAsset(BaseModel):
    id: str
    project_id: str
    name: str
    description: str
    time_of_day: str
    reference_image_path: str
    version: int
    is_current: bool
    created_at: str
    updated_at: str


class EpisodeScript(BaseModel):
    id: str
    project_id: str
    episode_number: int
    title: str
    synopsis: str
    dialogue_text: str
    status: PlanStatus
    script_version: int
    is_current: bool
    created_at: str
    updated_at: str


class ScriptScene(BaseModel):
    id: str
    script_id: str
    project_id: str
    episode_number: int
    scene_number: int
    location_name: str
    time_of_day: str
    character_names: list[str]
    action_text: str
    dialogue_text: str
    source_text: str
    created_at: str
    updated_at: str


class ParseSummary(BaseModel):
    project_id: str
    source_version: int
    character_count: int
    location_count: int
    scene_count: int
    script_count: int

