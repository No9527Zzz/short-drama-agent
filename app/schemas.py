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



class CharacterUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=4000)
    role_type: str = Field(default="supporting", max_length=40)
    voice_name: str = Field(default="", max_length=120)
    reference_image_path: str = Field(default="", max_length=500)


class LocationUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=4000)
    time_of_day: str = Field(default="", max_length=100)
    reference_image_path: str = Field(default="", max_length=500)


class EpisodeScriptUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    synopsis: str = Field(default="", max_length=4000)
    dialogue_text: str = Field(default="", max_length=10000)
    status: PlanStatus = "draft"


class ScriptSceneUpdate(BaseModel):
    location_name: str = Field(default="", max_length=160)
    time_of_day: str = Field(default="", max_length=100)
    character_names: list[str] = Field(default_factory=list)
    action_text: str = Field(default="", max_length=4000)
    dialogue_text: str = Field(default="", max_length=10000)



class StoryboardSummary(BaseModel):
    id: str
    project_id: str
    episode_number: int
    storyboard_version: int
    status: PlanStatus
    is_current: bool
    created_at: str
    updated_at: str


class ShotPlan(BaseModel):
    id: str
    storyboard_id: str
    project_id: str
    episode_number: int
    shot_number: int
    scene_number: int
    shot_type: str
    camera: str
    duration_seconds: int
    visual_description: str
    action_text: str
    dialogue_text: str
    character_names: list[str]
    location_name: str
    status: PlanStatus
    created_at: str
    updated_at: str


class ShotPlanUpdate(BaseModel):
    shot_type: str = Field(default="中景", max_length=40)
    camera: str = Field(default="固定", max_length=120)
    duration_seconds: int = Field(ge=1, le=60)
    visual_description: str = Field(default="", max_length=4000)
    action_text: str = Field(default="", max_length=4000)
    dialogue_text: str = Field(default="", max_length=10000)
    character_names: list[str] = Field(default_factory=list)
    location_name: str = Field(default="", max_length=160)
    status: PlanStatus = "draft"


class StoryboardGenerationSummary(BaseModel):
    project_id: str
    episode_number: int
    storyboard_version: int
    shot_count: int
    total_duration_seconds: int
    status: str

