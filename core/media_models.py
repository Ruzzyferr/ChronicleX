"""Faz 3: sahne ve medya pipeline modelleri."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

MotionType = Literal["zoom_in", "zoom_out", "pan_left", "pan_right"]
_MOTIONS = frozenset({"zoom_in", "zoom_out", "pan_left", "pan_right"})


class Scene(BaseModel):
    scene_id: int = Field(ge=1, le=99)
    duration: float = Field(ge=1.0, le=12.0)
    text: str = Field(min_length=1)
    image_prompt: str = Field(min_length=1)
    motion: MotionType = "zoom_in"

    @field_validator("motion", mode="before")
    @classmethod
    def coerce_motion(cls, v: object) -> str:
        s = str(v).strip().lower() if v is not None else "zoom_in"
        return s if s in _MOTIONS else "zoom_in"


class ScenesLLMResponse(BaseModel):
    scenes: list[Scene] = Field(default_factory=list)
