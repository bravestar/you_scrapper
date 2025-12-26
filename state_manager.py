"""
IYE State Manager - Durable state persistence for network resilience
Separates "durable state" from "live transport state"
"""
import os
import json
from typing import Optional, Dict
from datetime import datetime
from models import ExtractionState, PlayerArtifact
from config import IYEConfig

class StateManager:
    """
    Manages persistent state that survives network interruptions.
    Solves: "When connectivity drops, you risk losing progress"
    """
    
    def __init__(self, state_dir: str = IYEConfig.STATE_DIR):
        self.state_dir = state_dir
        self.player_dir = os.path.join(state_dir, "player_artifacts")
        self.job_dir = os.path.join(state_dir, "jobs")
        
        # Create directories
        os.makedirs(self.player_dir, exist_ok=True)
        os.makedirs(self.job_dir, exist_ok=True)
    
    def save_extraction_state(self, state: ExtractionState):
        """
        Persist extraction state to disk.
        Enables resume after network failure.
        """
        filepath = os.path.join(self.job_dir, f"{state.job_id}.json")
        
        with open(filepath, 'w') as f:
            json.dump(state.dict(), f, indent=2, default=str)
        
        print(f"[State] Saved extraction state: {state.job_id}")
    
    def load_extraction_state(self, job_id: str) -> Optional[ExtractionState]:
        """Load extraction state from disk"""
        filepath = os.path.join(self.job_dir, f"{job_id}.json")
        
        if not os.path.exists(filepath):
            return None
        
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        # Convert ISO datetime strings back to datetime objects
        if 'last_successful_request' in data and isinstance(data['last_successful_request'], str):
            data['last_successful_request'] = datetime.fromisoformat(data['last_successful_request'])
        
        return ExtractionState(**data)
    
    def delete_extraction_state(self, job_id: str):
        """Delete state after successful completion"""
        filepath = os.path.join(self.job_dir, f"{job_id}.json")
        if os.path.exists(filepath):
            os.remove(filepath)
            print(f"[State] Deleted completed job state: {job_id}")
    
    def save_player_artifact(self, artifact: PlayerArtifact):
        """
        Save player artifact with version tracking.
        Prevents redundant JS compilation.
        """
        filepath = os.path.join(self.player_dir, f"{artifact.player_version_id}.json")
        
        with open(filepath, 'w') as f:
            json.dump(artifact.dict(), f, indent=2, default=str)
        
        print(f"[State] Cached player artifact: {artifact.player_version_id[:12]}...")
    
    def load_player_artifact(self, version_id: str) -> Optional[PlayerArtifact]:
        """Load cached player artifact by version ID"""
        filepath = os.path.join(self.player_dir, f"{version_id}.json")
        
        if not os.path.exists(filepath):
            return None
        
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        # Convert datetime strings
        for date_field in ['created_at', 'last_validated']:
            if date_field in data and isinstance(data[date_field], str):
                data[date_field] = datetime.fromisoformat(data[date_field])
        
        artifact = PlayerArtifact(**data)
        
        # Check if artifact is still fresh
        age_seconds = (datetime.utcnow() - artifact.created_at).total_seconds()
        if age_seconds > IYEConfig.PLAYER_CACHE_TTL:
            print(f"[State] Player artifact expired, will refresh")
            return None
        
        return artifact
    
    def list_incomplete_jobs(self) -> Dict[str, ExtractionState]:
        """
        List all incomplete extraction jobs.
        Useful for recovery after crash/restart.
        """
        incomplete = {}
        
        for filename in os.listdir(self.job_dir):
            if not filename.endswith('.json'):
                continue
            
            job_id = filename[:-5]  # Remove .json
            state = self.load_extraction_state(job_id)
            
            if state and state.status in ['pending', 'in_progress']:
                incomplete[job_id] = state
        
        return incomplete
    
    def get_download_resume_info(self, job_id: str, target_filename: str) -> tuple:
        """
        Get information needed to resume a download.
        Returns: (offset, etag, last_modified)
        """
        state = self.load_extraction_state(job_id)
        
        if not state:
            return (0, None, None)
        
        # Check if partial file exists
        part_file = target_filename + IYEConfig.DOWNLOAD_TEMP_SUFFIX
        if os.path.exists(part_file):
            actual_size = os.path.getsize(part_file)
            # Use actual file size if state is inconsistent
            offset = max(actual_size, state.bytes_completed)
        else:
            offset = 0
        
        return (offset, state.etag, state.last_modified)
    
    def update_download_progress(
        self, 
        job_id: str, 
        bytes_completed: int,
        etag: Optional[str] = None,
        last_modified: Optional[str] = None
    ):
        """
        Update download progress in state.
        Call periodically during download (e.g., every chunk).
        """
        state = self.load_extraction_state(job_id)
        
        if not state:
            print(f"[State] Warning: Cannot update progress for unknown job {job_id}")
            return
        
        state.bytes_completed = bytes_completed
        state.last_successful_request = datetime.utcnow()
        
        if etag:
            state.etag = etag
        if last_modified:
            state.last_modified = last_modified
        
        state.status = "in_progress"
        
        self.save_extraction_state(state)
    
    def cleanup_old_artifacts(self, max_age_hours: int = 24):
        """
        Clean up expired player artifacts.
        Prevents state directory from growing unbounded.
        """
        cutoff = datetime.utcnow().timestamp() - (max_age_hours * 3600)
        
        for filename in os.listdir(self.player_dir):
            filepath = os.path.join(self.player_dir, filename)
            
            if os.path.getmtime(filepath) < cutoff:
                os.remove(filepath)
                print(f"[State] Cleaned up old artifact: {filename}")
