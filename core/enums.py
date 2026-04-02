from enum import Enum


class PipelinePhase(str, Enum):
    DISCOVERY = "discovery"
    SCRIPTING = "scripting"
    RENDER = "render"
    PUBLISH = "publish"


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
