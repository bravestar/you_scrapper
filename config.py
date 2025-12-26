"""
IYE Configuration - Centralized settings for the extraction engine
"""
from typing import Dict
import os

class IYEConfig:
    """Enterprise-grade configuration with production defaults"""
    
    # === Network Resilience ===
    CONNECT_TIMEOUT = 10.0  # seconds
    READ_TIMEOUT = 30.0
    TOTAL_TIMEOUT = 60.0
    MAX_RETRIES = 3
    RETRY_BACKOFF_BASE = 2.0  # exponential backoff multiplier
    RETRY_JITTER_MAX = 1.0  # random jitter to prevent thundering herd
    
    # === Circuit Breaker ===
    CIRCUIT_BREAKER_THRESHOLD = 5  # failures before opening circuit
    CIRCUIT_BREAKER_TIMEOUT = 60.0  # seconds before attempting reset
    CIRCUIT_BREAKER_RECOVERY_THRESHOLD = 2  # successes to close circuit
    
    # === Download Manager ===
    CHUNK_SIZE = 1024 * 1024  # 1MB chunks
    MAX_CONCURRENT_DOWNLOADS = 3
    DOWNLOAD_TEMP_SUFFIX = ".part"
    
    # === Player Artifact Cache ===
    PLAYER_CACHE_TTL = 3600  # 1 hour - refresh player artifacts periodically
    PLAYER_CACHE_SIZE = 10  # LRU cache size for compiled artifacts
    
    # === State Persistence ===
    STATE_DIR = os.path.join(os.path.dirname(__file__), ".iye_state")
    ENABLE_STATE_PERSISTENCE = True
    
    # === Performance ===
    JS_EXECUTION_TIMEOUT = 10.0  # seconds for JS compilation
    MAX_JS_WORKERS = 2  # dedicated thread pool for JS execution
    
    # === YouTube Client Versions (Updated 2025) ===
    YOUTUBE_CLIENT_VERSION = "2.20250115.01.00"
    YOUTUBE_API_KEY = "AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8"  # Public web client key
    
    # === TLS Fingerprints ===
    TLS_IMPERSONATIONS = [
        "chrome120",
        "chrome119", 
        "safari17_0",
        "safari17_2"
    ]
    
    # === Detection Mitigation ===
    HUMAN_DELAY_MIN = 0.8  # seconds
    HUMAN_DELAY_MAX = 2.3
    PREFLIGHT_DELAY = 0.05  # tiny delay after OPTIONS
    
    # === Logging ===
    LOG_LEVEL = "INFO"
    ENABLE_TELEMETRY = True
    
    @classmethod
    def ensure_state_directory(cls):
        """Create state directory if it doesn't exist"""
        if cls.ENABLE_STATE_PERSISTENCE:
            os.makedirs(cls.STATE_DIR, exist_ok=True)
