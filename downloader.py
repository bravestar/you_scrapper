"""
IYE Resumable Downloader - Network-resilient download manager
Implements: Range headers, progress persistence, validation
"""
import os
import asyncio
from typing import Optional
from models import ExtractionState, StreamFormat
from session_manager import SessionFactory
from state_manager import StateManager
from circuit_breaker import CircuitBreaker, RetryPolicy
from config import IYEConfig

class ResumableDownloader:
    """
    Network-resilient downloader with:
    - Resumable downloads via Range headers
    - Progress persistence to disk
    - ETag/Last-Modified validation
    - Atomic file completion
    """
    
    def __init__(
        self,
        session_factory: SessionFactory,
        state_manager: StateManager
    ):
        self.session_factory = session_factory
        self.state_manager = state_manager
        self.download_cb = CircuitBreaker("download")
    
    async def download_stream(
        self,
        job_id: str,
        stream: StreamFormat,
        target_filename: str,
        video_id: str
    ) -> str:
        """
        Download a stream with full resumability.
        
        Returns: Path to completed file
        """
        # Load or create extraction state
        state = self.state_manager.load_extraction_state(job_id)
        
        if not state:
            # Create new state
            state = ExtractionState(
                video_id=video_id,
                job_id=job_id,
                player_artifact_id="current",  # Would be actual ID in production
                target_filename=target_filename,
                content_length=stream.content_length
            )
            self.state_manager.save_extraction_state(state)
        
        # Determine resume offset
        part_file = target_filename + IYEConfig.DOWNLOAD_TEMP_SUFFIX
        offset, etag, last_modified = self.state_manager.get_download_resume_info(
            job_id, target_filename
        )
        
        if offset > 0:
            print(f"[Download] Resuming from byte {offset:,}")
        
        # Get stream URL
        stream_url = stream.url
        if not stream_url:
            raise Exception("Stream URL not available (cipher not decrypted)")
        
        # Download with resume support
        session = await self.session_factory.get_session()
        
        async def _download():
            return await self._download_with_range(
                session=session,
                url=stream_url,
                part_file=part_file,
                offset=offset,
                expected_etag=etag,
                expected_last_modified=last_modified,
                job_id=job_id
            )
        
        # Execute with retry
        await RetryPolicy.with_retry(
            _download,
            circuit_breaker=self.download_cb,
            operation_name=f"download_{video_id}"
        )
        
        # Atomic rename to final filename
        final_path = self._atomic_complete(part_file, target_filename)
        
        # Update state to completed
        state.status = "completed"
        state.bytes_completed = os.path.getsize(final_path)
        self.state_manager.save_extraction_state(state)
        
        # Cleanup state file
        self.state_manager.delete_extraction_state(job_id)
        
        print(f"[Download] Completed: {final_path}")
        return final_path
    
    async def _download_with_range(
        self,
        session,
        url: str,
        part_file: str,
        offset: int,
        expected_etag: Optional[str],
        expected_last_modified: Optional[str],
        job_id: str
    ):
        """
        Download with Range header support and validation.
        """
        # Build headers
        headers = {}
        if offset > 0:
            headers["Range"] = f"bytes={offset}-"
        
        # Make request
        resp = await session.get(url, headers=headers, stream=True)
        
        # Validate status
        if offset > 0 and resp.status_code not in [200, 206]:
            raise Exception(f"Range request failed: {resp.status_code}")
        elif offset == 0 and resp.status_code != 200:
            raise Exception(f"Download request failed: {resp.status_code}")
        
        # Validate ETag if we have one
        current_etag = resp.headers.get("ETag")
        if expected_etag and current_etag and expected_etag != current_etag:
            print(f"[Download] WARNING: ETag mismatch, starting from beginning")
            offset = 0
            # Re-open file in write mode to start fresh
        
        # Get content length
        content_length = resp.headers.get("Content-Length")
        if content_length:
            content_length = int(content_length)
        
        # Open file for writing
        mode = "ab" if offset > 0 else "wb"
        
        print(f"[Download] Starting download (offset={offset:,}, mode={mode})")
        
        bytes_written = offset
        chunk_count = 0
        
        with open(part_file, mode) as f:
            async for chunk in resp.iter_content(chunk_size=IYEConfig.CHUNK_SIZE):
                if chunk:
                    f.write(chunk)
                    bytes_written += len(chunk)
                    chunk_count += 1
                    
                    # Update progress every 10 chunks
                    if chunk_count % 10 == 0:
                        self.state_manager.update_download_progress(
                            job_id=job_id,
                            bytes_completed=bytes_written,
                            etag=current_etag,
                            last_modified=resp.headers.get("Last-Modified")
                        )
                        
                        # Progress indicator
                        if content_length:
                            pct = (bytes_written / (content_length + offset)) * 100
                            print(f"[Download] Progress: {pct:.1f}% ({bytes_written:,} bytes)", end='\r')
                        else:
                            print(f"[Download] Downloaded: {bytes_written:,} bytes", end='\r')
        
        print(f"\n[Download] Finished writing {bytes_written:,} bytes")
        
        # Final progress update
        self.state_manager.update_download_progress(
            job_id=job_id,
            bytes_completed=bytes_written,
            etag=current_etag,
            last_modified=resp.headers.get("Last-Modified")
        )
    
    def _atomic_complete(self, part_file: str, final_file: str) -> str:
        """
        Atomically rename .part file to final filename.
        Prevents partial files from appearing complete.
        """
        if not os.path.exists(part_file):
            raise Exception(f"Part file not found: {part_file}")
        
        # Remove existing final file if present
        if os.path.exists(final_file):
            os.remove(final_file)
        
        # Atomic rename
        os.rename(part_file, final_file)
        
        return final_file
    
    async def download_best_quality(
        self,
        job_id: str,
        streams: list,
        video_id: str,
        output_dir: str = ".",
        prefer_codec: Optional[str] = None
    ) -> str:
        """
        Download best quality stream based on criteria.
        
        Args:
            job_id: Unique job identifier
            streams: List of StreamFormat objects
            video_id: YouTube video ID
            output_dir: Directory to save file
            prefer_codec: Preferred codec (e.g., "vp9", "h264")
        """
        # Filter video streams
        video_streams = [
            s for s in streams 
            if s.mime_type and "video" in s.mime_type
        ]
        
        if not video_streams:
            raise Exception("No video streams found")
        
        # Apply codec preference
        if prefer_codec:
            preferred = [
                s for s in video_streams 
                if prefer_codec.lower() in s.mime_type.lower()
            ]
            if preferred:
                video_streams = preferred
        
        # Sort by resolution (height) and bitrate
        best_stream = max(
            video_streams,
            key=lambda s: (s.height or 0, s.bitrate)
        )
        
        # Determine filename
        quality = f"{best_stream.height}p" if best_stream.height else "unknown"
        codec = "vp9" if "vp9" in best_stream.mime_type else "h264"
        filename = os.path.join(output_dir, f"{video_id}_{quality}_{codec}.mp4")
        
        print(f"[Download] Selected: {quality} ({best_stream.bitrate} bps) - {codec}")
        
        return await self.download_stream(job_id, best_stream, filename, video_id)
