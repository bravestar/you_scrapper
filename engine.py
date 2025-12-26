"""
IYE InnerTube Engine - Core YouTube API interaction layer
Implements InnerTube protocol with full bot defeat techniques
"""
import asyncio
from typing import Dict, Optional
from models import VideoDetails, StreamFormat, ExtractionResult, TelemetryContext, DetectionRisk
from session_manager import SessionFactory
from player_artifacts import PlayerArtifactManager
from circuit_breaker import CircuitBreaker, RetryPolicy
from gems import ExtractionGems, BotDefeatTechniques
from config import IYEConfig

class InnerTubeEngine:
    """
    Core extraction engine using InnerTube API.
    Bypasses HTML parsing with internal JSON endpoints.
    """
    
    def __init__(
        self,
        session_factory: SessionFactory,
        player_manager: PlayerArtifactManager,
        enable_mobile: bool = False
    ):
        self.session_factory = session_factory
        self.player_manager = player_manager
        self.enable_mobile = enable_mobile
        
        # Circuit breakers for different endpoints
        self.player_cb = CircuitBreaker("player_endpoint")
        self.browse_cb = CircuitBreaker("browse_endpoint")
        
        # Telemetry tracking
        self.telemetry = TelemetryContext()
    
    async def fetch_video_data(self, video_id: str) -> Dict:
        """
        Fetch video data using InnerTube player endpoint.
        Main entry point for video extraction.
        """
        session = await self.session_factory.get_session()
        
        # Get current player artifact
        artifact = await self.player_manager.get_current_artifact()
        
        # Build context with all anti-bot signals
        context = BotDefeatTechniques.build_innertube_context(
            po_token=ExtractionGems.generate_po_token()
        )
        
        # Build request payload
        payload = {
            "context": context,
            "videoId": video_id,
            "playbackContext": {
                "contentPlaybackContext": {
                    "signatureTimestamp": artifact.extracted_sts
                }
            },
            "contentCheckOk": True,
            "racyCheckOk": True
        }
        
        # InnerTube player endpoint
        url = f"https://www.youtube.com/youtubei/v1/player?key={IYEConfig.YOUTUBE_API_KEY}"
        
        # Human delay before request
        await ExtractionGems.human_delay()
        
        # Preflight OPTIONS for CORS mimicry
        await ExtractionGems.preflight_options(session, url)
        
        # Execute with retry and circuit breaker
        async def _fetch():
            import time
            start = time.time()
            
            resp = await session.post(url, json=payload)
            
            # Track telemetry
            self.telemetry.response_time = time.time() - start
            self.telemetry.status_code = resp.status_code
            
            if resp.status_code == 429:
                self.telemetry.rate_limited = True
                raise Exception("Rate limited")
            
            if resp.status_code != 200:
                raise Exception(f"Player API returned {resp.status_code}")
            
            data = resp.json()
            
            # Check for schema drift
            if BotDefeatTechniques.detect_schema_drift(data):
                print("[Engine] WARNING: Schema drift detected, may need updates")
            
            return data
        
        return await RetryPolicy.with_retry(
            _fetch,
            circuit_breaker=self.player_cb,
            operation_name=f"fetch_video_{video_id}"
        )
    
    async def extract_video(self, video_id: str) -> ExtractionResult:
        """
        Complete video extraction with all metadata and streams.
        Returns enriched result with telemetry and handoffs.
        """
        try:
            # Fetch raw data
            data = await self.fetch_video_data(video_id)
            
            # Extract metadata
            video_details_raw = data.get("videoDetails", {})
            metadata = VideoDetails(**video_details_raw)
            
            # Extract streams
            streaming_data = data.get("streamingData", {})
            adaptive_formats = streaming_data.get("adaptiveFormats", [])
            
            streams = []
            for fmt in adaptive_formats:
                try:
                    stream = StreamFormat(**fmt)
                    streams.append(stream)
                except Exception as e:
                    print(f"[Engine] Failed to parse stream format: {e}")
                    continue
            
            # Get player artifact info
            artifact = await self.player_manager.get_current_artifact()
            
            # Calculate detection risk
            risk_score = self.telemetry.calculate_risk_score()
            if risk_score < 0.3:
                self.telemetry.detection_risk = DetectionRisk.LOW
            elif risk_score < 0.6:
                self.telemetry.detection_risk = DetectionRisk.MEDIUM
            elif risk_score < 0.8:
                self.telemetry.detection_risk = DetectionRisk.HIGH
            else:
                self.telemetry.detection_risk = DetectionRisk.CRITICAL
            
            # Build result
            result = ExtractionResult(
                metadata=metadata,
                streams=streams,
                sts=artifact.extracted_sts,
                player_version_id=artifact.player_version_id,
                telemetry=self.telemetry
            )
            
            print(f"[Engine] Extracted: {metadata.title} ({len(streams)} streams)")
            print(f"[Engine] Detection Risk: {self.telemetry.detection_risk.value}")
            
            return result
            
        except Exception as e:
            print(f"[Engine] Extraction failed: {e}")
            raise
    
    async def get_dash_manifest(self, video_id: str) -> Optional[str]:
        """
        Adaptive Bitrate Segment Sniping - get DASH manifest.
        Alternative approach that bypasses signature throttling.
        """
        session = await self.session_factory.get_session()
        artifact = await self.player_manager.get_current_artifact()
        
        context = BotDefeatTechniques.build_innertube_context()
        
        payload = {
            "context": context,
            "videoId": video_id,
            "params": "8AEB",  # Magic param for DASH manifest
            "contentCheckOk": True,
            "racyCheckOk": True,
            "playbackContext": {
                "contentPlaybackContext": {
                    "signatureTimestamp": artifact.extracted_sts
                }
            }
        }
        
        url = f"https://www.youtube.com/youtubei/v1/player?key={IYEConfig.YOUTUBE_API_KEY}"
        
        async def _fetch():
            resp = await session.post(url, json=payload)
            if resp.status_code != 200:
                raise Exception(f"DASH manifest request failed: {resp.status_code}")
            
            data = resp.json()
            return data.get("streamingData", {}).get("dashManifestUrl")
        
        return await RetryPolicy.with_retry(
            _fetch,
            circuit_breaker=self.player_cb,
            operation_name=f"dash_manifest_{video_id}"
        )
    
    async def extract_from_embed(self, video_id: str) -> Dict:
        """
        Alternative extraction via embed endpoint.
        Lower security, useful as fallback.
        """
        session = await self.session_factory.get_session()
        
        # Try to get BotGuard token from embed
        bg_token = await ExtractionGems.extract_botguard_token(session, video_id)
        
        embed_url = f"https://www.youtube.com/embed/{video_id}"
        
        async def _fetch():
            resp = await session.get(embed_url)
            if resp.status_code != 200:
                raise Exception(f"Embed request failed: {resp.status_code}")
            
            # Parse embed page for player config
            text = resp.text if hasattr(resp, 'text') else resp.content.decode('utf-8')
            
            # Extract ytInitialPlayerResponse from embed page
            import json
            import re
            
            match = re.search(r'ytInitialPlayerResponse\s*=\s*({.+?});', text, re.DOTALL)
            if match:
                return json.loads(match.group(1))
            
            return {}
        
        return await RetryPolicy.with_retry(
            _fetch,
            circuit_breaker=self.browse_cb,
            operation_name=f"embed_{video_id}"
        )
    
    async def get_context(self) -> Dict:
        """Get InnerTube context"""
        return BotDefeatTechniques.build_innertube_context(
            po_token=ExtractionGems.generate_po_token()
        )
