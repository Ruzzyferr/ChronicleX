class ChannelAutomationError(Exception):
    """Base error for the channel automation app."""


class ConfigError(ChannelAutomationError):
    """Invalid or missing configuration."""


class PipelineError(ChannelAutomationError):
    """Pipeline step failed."""


class MediaPipelineError(ChannelAutomationError):
    """Faz 3 medya üretimi veya FFmpeg hatası."""
