"""
IYE Data Models - Type-safe schemas with version tracking
"""
from pydantic import BaseModel, Field, HttpUrl
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum

class StreamFormat(BaseModel):
    """Represents a specific video/audio stream variant"""
    itag: int
    url: Optional[str] = None
    mime_type: str = Field(alias="mimeType")
    bitrate: int
    width: Optional[int] = None
    height: Optional[int] = None
    signature_cipher: Optional[str] = Field(None, alias="signatureCipher")
    content_length: Optional[int] = Field(None, alias="contentLength")
    quality: Optional[str] = None
    fps: Optional[int] = None
    
    class Config:
        populate_by_name = True
        extra = "allow"

class VideoDetails(BaseModel):
    """Standardized metadata for any YouTube video"""
    video_id: str = Field(alias="videoId")
    title: str
    length_seconds: int = Field(alias="lengthSeconds")
    keywords: List[str] = []
    channel_id: str = Field(alias="channelId")
    short_description: str = Field(alias="shortDescription")
    view_count: int = Field(alias="viewCount")
    author: str
    is_live_content: Optional[bool] = Field(None, alias="isLiveContent")
    
    class Config:
        populate_by_name = True
        extra = "allow"

class PlayerArtifact(BaseModel):
    """
    Version-safe player artifact with integrity tracking.
    This solves the "STS synchronization from version control" problem.
    """
    player_url: str
    player_version_id: str  # SHA-256 hash of JS bytes
    extracted_sts: str
    decipher_function_code: Optional[str] = None
    n_function_code: Optional[str] = None
    extraction_method_version: str = "2.0"  # Internal version for invalidation
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_validated: datetime = Field(default_factory=datetime.utcnow)
    failure_count: int = 0
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class ExtractionState(BaseModel):
    """
    Durable state for network-resilient extraction.
    Persisted to disk and survives connectivity drops.
    """
    video_id: str
    job_id: str
    player_artifact_id: str  # Reference to PlayerArtifact
    target_filename: str
    bytes_completed: int = 0
    content_length: Optional[int] = None
    etag: Optional[str] = None
    last_modified: Optional[str] = None
    last_successful_request: datetime = Field(default_factory=datetime.utcnow)
    retry_count: int = 0
    status: str = "pending"  # pending, in_progress, completed, failed
    error_message: Optional[str] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class DetectionRisk(str, Enum):
    """Risk levels for adaptive routing"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class TelemetryContext(BaseModel):
    """
    Telemetry breadcrumbs for handoff intelligence.
    Enables downstream systems to make adaptive decisions.
    """
    captcha_triggered: bool = False
    rate_limited: bool = False
    response_time: float = 0.0
    status_code: int = 200
    missing_headers: List[str] = []
    detection_risk: DetectionRisk = DetectionRisk.LOW
    retry_count: int = 0
    
    def calculate_risk_score(self) -> float:
        """
        Calculate numerical risk score for routing decisions.
        Score range: 0.0 (safe) to 1.0 (critical)
        """
        score = 0.0
        if self.captcha_triggered:
            score += 0.4
        if self.rate_limited:
            score += 0.6
        if self.response_time > 2.0:
            score += 0.2
        if len(self.missing_headers) > 2:
            score += 0.3
        return min(score, 1.0)

class LazyStreamHandoff(BaseModel):
    """
    Lazy decryption delegation for parallel processing.
    Don't decrypt during scraping - defer to worker pool.
    """
    encrypted_signature_cipher: Optional[str] = None
    decipher_func_id: str  # Redis/cache key for shared function
    n_param_func_id: Optional[str] = None
    sts_version: str
    itag: int
    quality_rank: int = 99
    base_url: Optional[str] = None
    priority: int = 5  # 1=highest, 10=lowest

class StreamMutationHandoff(BaseModel):
    """
    Stream mutation protocol - pass instructions, not URLs.
    URLs expire; mutation instructions regenerate on-demand.
    """
    itag: int
    cipher_components: Dict[str, str]
    sts_version: str
    n_function_code: Optional[str] = None
    session_cookies: Dict[str, str]
    expiry_timestamp: float
    player_version_id: str

class ExtractionResult(BaseModel):
    """
    Final handoff object with enriched context.
    Includes telemetry and multiple handoff strategies.
    """
    metadata: VideoDetails
    streams: List[StreamFormat]
    sts: str
    player_version_id: str
    telemetry: TelemetryContext
    lazy_handoffs: List[LazyStreamHandoff] = []
    mutation_handoffs: List[StreamMutationHandoff] = []
    extracted_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        populate_by_name = True
        extra = "allow"
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
