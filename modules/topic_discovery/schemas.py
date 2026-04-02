"""Structured models for discovery and verification I/O."""

from __future__ import annotations

from pydantic import BaseModel, Field


class RawCandidate(BaseModel):
    title: str
    summary: str = ""
    event_year: int | None = None
    country: str | None = None
    region: str | None = None
    category: str | None = None
    subcategory: str | None = None
    people_involved: str | None = None
    source_1: str | None = None
    source_2: str | None = None
    source_3: str | None = None
    shock_score: int = Field(default=5, ge=0, le=10)
    fear_score: int = Field(default=5, ge=0, le=10)
    clarity_score: int = Field(default=5, ge=0, le=10)
    visual_score: int = Field(default=5, ge=0, le=10)


class DiscoveryLLMResponse(BaseModel):
    candidates: list[RawCandidate] = Field(default_factory=list)


class VerificationItem(BaseModel):
    index: int = Field(ge=0)
    verification_score: int = Field(ge=0, le=10)
    is_verified: bool
    notes: str = ""


class VerificationLLMResponse(BaseModel):
    results: list[VerificationItem] = Field(default_factory=list)


class ScoredCandidate(BaseModel):
    raw: RawCandidate
    novelty_score: int = Field(ge=0, le=10)
    verification_score: int = Field(ge=0, le=10)
    is_verified: bool = False

    def composite_score(self) -> float:
        r = self.raw
        return (
            0.22 * r.shock_score
            + 0.10 * r.fear_score
            + 0.18 * r.clarity_score
            + 0.18 * r.visual_score
            + 0.17 * self.novelty_score
            + 0.15 * self.verification_score
        )
