"""
IYE Main - Orchestration layer for complete extraction workflow
Demonstrates how all components work together
"""
import asyncio
import uuid
from typing import Optional
from datetime import datetime

from config import IYEConfig
from session_manager import SessionFactory
from state_manager import StateManager
from player_artifacts import PlayerArtifactManager
from engine import InnerTubeEngine
from downloader import ResumableDownloader
from models import ExtractionResult

class IYEOrchestrator:
    """
    High-level orchestrator that coordinates all subsystems.
    This is what you'd use in production.
    """
    
    def __init__(
        self,
        enable_mobile: bool = False,
        proxy: Optional[str] = None,
        output_dir: str = "./downloads"
    ):
        # Ensure state directory exists
        IYEConfig.ensure_state_directory()
        
        # Initialize core components
        self.session_factory = SessionFactory(
            impersonate="chrome120",
            proxy=proxy,
            enable_mobile=enable_mobile
        )
        
        self.state_manager = StateManager()
        
        self.player_manager = PlayerArtifactManager(
            session_factory=self.session_factory,
            state_manager=self.state_manager
        )
        
        self.engine = InnerTubeEngine(
            session_factory=self.session_factory,
            player_manager=self.player_manager,
            enable_mobile=enable_mobile
        )
        
        self.downloader = ResumableDownloader(
            session_factory=self.session_factory,
            state_manager=self.state_manager
        )
        
        self.output_dir = output_dir
    
    async def extract_video(self, video_id: str) -> ExtractionResult:
        """
        Extract complete video metadata and streams.
        Does NOT download - just gets extraction result.
        """
        print(f"\n{'='*60}")
        print(f"[IYE] Starting extraction: {video_id}")
        print(f"{'='*60}\n")
        
        result = await self.engine.extract_video(video_id)
        
        print(f"\n[IYE] Extraction Complete:")
        print(f"  Title: {result.metadata.title}")
        print(f"  Author: {result.metadata.author}")
        print(f"  Duration: {result.metadata.length_seconds}s")
        print(f"  Views: {result.metadata.view_count:,}")
        print(f"  Streams: {len(result.streams)}")
        print(f"  STS Version: {result.sts}")
        print(f"  Detection Risk: {result.telemetry.detection_risk.value}")
        
        return result
    
    async def extract_and_download(
        self,
        video_id: str,
        quality: Optional[str] = None,
        prefer_codec: Optional[str] = None
    ) -> str:
        """
        Complete workflow: extract + download best quality.
        
        Args:
            video_id: YouTube video ID
            quality: Desired quality (e.g., "1080p", "720p")
            prefer_codec: Preferred codec (e.g., "vp9", "h264")
        
        Returns: Path to downloaded file
        """
        # Extract metadata and streams
        result = await self.extract_video(video_id)
        
        # Generate job ID for resumability
        job_id = f"{video_id}_{uuid.uuid4().hex[:8]}"
        
        print(f"\n[IYE] Starting download (Job: {job_id})...")
        
        # Download best quality
        filepath = await self.downloader.download_best_quality(
            job_id=job_id,
            streams=result.streams,
            video_id=video_id,
            output_dir=self.output_dir,
            prefer_codec=prefer_codec
        )
        
        print(f"\n{'='*60}")
        print(f"[IYE] SUCCESS: {filepath}")
        print(f"{'='*60}\n")
        
        return filepath
    
    async def resume_incomplete_jobs(self):
        """
        Resume any incomplete download jobs.
        Useful for recovery after crash/network failure.
        """
        incomplete = self.state_manager.list_incomplete_jobs()
        
        if not incomplete:
            print("[IYE] No incomplete jobs to resume")
            return
        
        print(f"[IYE] Found {len(incomplete)} incomplete job(s)")
        
        for job_id, state in incomplete.items():
            print(f"\n[IYE] Resuming job: {job_id}")
            print(f"  Video: {state.video_id}")
            print(f"  Progress: {state.bytes_completed:,} bytes")
            
            try:
                # Re-extract to get fresh streams
                result = await self.extract_video(state.video_id)
                
                # Find the stream we were downloading
                # In production, you'd store itag in state
                # For now, just download best quality
                filepath = await self.downloader.download_best_quality(
                    job_id=job_id,
                    streams=result.streams,
                    video_id=state.video_id,
                    output_dir=self.output_dir
                )
                
                print(f"[IYE] Resumed and completed: {filepath}")
                
            except Exception as e:
                print(f"[IYE] Failed to resume {job_id}: {e}")
    
    async def extract_multiple(self, video_ids: list, max_concurrent: int = 3):
        """
        Extract multiple videos concurrently.
        Demonstrates batch processing.
        """
        print(f"[IYE] Extracting {len(video_ids)} videos (max {max_concurrent} concurrent)")
        
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def extract_with_semaphore(vid):
            async with semaphore:
                try:
                    return await self.extract_video(vid)
                except Exception as e:
                    print(f"[IYE] Failed to extract {vid}: {e}")
                    return None
        
        tasks = [extract_with_semaphore(vid) for vid in video_ids]
        results = await asyncio.gather(*tasks)
        
        successful = [r for r in results if r is not None]
        print(f"\n[IYE] Batch complete: {len(successful)}/{len(video_ids)} successful")
        
        return successful
    
    async def close(self):
        """Cleanup all resources"""
        await self.session_factory.close()
        await self.player_manager.close()
        print("[IYE] Shutdown complete")

# ============================================================================
# Command-line interface examples
# ============================================================================

async def example_extract_only():
    """Example: Extract metadata without downloading"""
    iye = IYEOrchestrator()
    
    try:
        result = await iye.extract_video("dQw4w9WgXcQ")
        
        # Access the data
        print(f"\nAvailable streams:")
        for stream in result.streams[:5]:  # Show first 5
            print(f"  {stream.quality} - {stream.mime_type} - {stream.bitrate} bps")
        
    finally:
        await iye.close()

async def example_extract_and_download():
    """Example: Complete extraction and download"""
    iye = IYEOrchestrator(output_dir="./videos")
    
    try:
        filepath = await iye.extract_and_download(
            video_id="dQw4w9WgXcQ",
            prefer_codec="vp9"
        )
        print(f"Downloaded to: {filepath}")
        
    finally:
        await iye.close()

async def example_batch_extraction():
    """Example: Batch extract multiple videos"""
    iye = IYEOrchestrator()
    
    video_ids = [
        "dQw4w9WgXcQ",
        "9bZkp7q19f0",
        "kJQP7kiw5Fk"
    ]
    
    try:
        results = await iye.extract_multiple(video_ids, max_concurrent=2)
        
        for result in results:
            if result:
                print(f"{result.metadata.title} - {len(result.streams)} streams")
        
    finally:
        await iye.close()

async def example_resume_after_failure():
    """Example: Resume incomplete downloads after network failure"""
    iye = IYEOrchestrator()
    
    try:
        await iye.resume_incomplete_jobs()
    finally:
        await iye.close()

async def main():
    """
    Main entry point - demonstrates basic usage
    """
    print("\n" + "="*60)
    print("IYE: InnerTube YouTube Extractor (2025 Complete Edition)")
    print("Enterprise-grade extraction with network resilience")
    print("="*60 + "\n")
    
    # Example: Extract and download
    await example_extract_and_download()
    
    # Or just extract metadata:
    # await example_extract_only()
    
    # Or batch process:
    # await example_batch_extraction()
    
    # Or resume failed jobs:
    # await example_resume_after_failure()

if __name__ == "__main__":
    asyncio.run(main())
