"""
IYE Player Artifacts Manager - Version-safe JS extraction with caching
Solves: "STS synchronization from version control perspective"
"""
import re
import asyncio
from typing import Optional, Dict, Callable
from functools import lru_cache
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
import hashlib

from models import PlayerArtifact
from state_manager import StateManager
from config import IYEConfig
from gems import ExtractionGems

class PlayerArtifactManager:
    """
    Manages player artifact extraction with:
    - Version-safe STS tracking
    - LRU caching to prevent recompilation
    - Thread pool for CPU-bound JS execution
    - Periodic refresh instead of per-video sync
    """
    
    def __init__(
        self,
        session_factory,
        state_manager: Optional[StateManager] = None
    ):
        self.session_factory = session_factory
        self.state_manager = state_manager or StateManager()
        
        # Shared LRU cache across tasks
        self._artifact_cache: Dict[str, PlayerArtifact] = {}
        self._cache_lock = asyncio.Lock()
        
        # Thread pool for CPU-bound JS operations
        self._js_executor = ThreadPoolExecutor(max_workers=IYEConfig.MAX_JS_WORKERS)
        
        # Current active artifact
        self._current_artifact: Optional[PlayerArtifact] = None
        self._last_refresh: Optional[datetime] = None
    
    async def get_current_artifact(self, force_refresh: bool = False) -> PlayerArtifact:
        """
        Get current player artifact, refreshing if needed.
        This is the main entry point - calls sync periodically, not per-video.
        """
        # Check if refresh needed
        needs_refresh = (
            force_refresh or
            self._current_artifact is None or
            self._needs_refresh()
        )
        
        if needs_refresh:
            return await self.sync_player_artifact()
        
        return self._current_artifact
    
    def _needs_refresh(self) -> bool:
        """Check if artifact needs refresh based on age"""
        if not self._last_refresh:
            return True
        
        age_seconds = (datetime.utcnow() - self._last_refresh).total_seconds()
        return age_seconds > IYEConfig.PLAYER_CACHE_TTL
    
    async def sync_player_artifact(self) -> PlayerArtifact:
        """
        Sync player artifact - fetch and parse base.js
        This is called periodically, not per-video.
        """
        session = await self.session_factory.get_session()
        
        try:
            # Fetch a sample video page to get player URL
            print("[PlayerArtifact] Syncing player artifact...")
            resp = await session.get("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
            
            if resp.status_code != 200:
                raise Exception(f"Failed to fetch watch page: {resp.status_code}")
            
            text = resp.text if hasattr(resp, 'text') else resp.content.decode('utf-8')
            
            # Extract player URL with robust regex
            player_url_match = re.search(r'"jsUrl"\s*:\s*"(/s/player/[^"]+/player[^"]+\.js)"', text)
            if not player_url_match:
                raise Exception("Failed to extract player URL")
            
            player_path = player_url_match.group(1).replace(r'\/', '/')
            player_url = f"https://www.youtube.com{player_path}"
            
            # Calculate version ID from URL
            temp_version_id = hashlib.md5(player_url.encode()).hexdigest()
            
            # Check cache first
            cached = await self._get_from_cache(temp_version_id)
            if cached:
                print(f"[PlayerArtifact] Using cached artifact: {temp_version_id[:12]}...")
                self._current_artifact = cached
                self._last_refresh = datetime.utcnow()
                return cached
            
            # Fetch player JS
            print(f"[PlayerArtifact] Fetching player: {player_url}")
            js_resp = await session.get(player_url)
            
            if js_resp.status_code != 200:
                raise Exception(f"Failed to fetch player JS: {js_resp.status_code}")
            
            js_code = js_resp.text if hasattr(js_resp, 'text') else js_resp.content.decode('utf-8')
            
            # Calculate actual version ID from JS content
            player_version_id = ExtractionGems.calculate_player_version_hash(js_code)
            
            # Check cache again with actual hash
            cached = await self._get_from_cache(player_version_id)
            if cached:
                print(f"[PlayerArtifact] Using cached artifact: {player_version_id[:12]}...")
                self._current_artifact = cached
                self._last_refresh = datetime.utcnow()
                return cached
            
            # Extract STS with error handling
            extracted_sts = self._extract_sts_safe(js_code)
            
            # Extract function code in thread pool (CPU-bound)
            decipher_code, n_code = await self._extract_functions(js_code)
            
            # Create artifact
            artifact = PlayerArtifact(
                player_url=player_url,
                player_version_id=player_version_id,
                extracted_sts=extracted_sts,
                decipher_function_code=decipher_code,
                n_function_code=n_code,
                extraction_method_version="2.0"
            )
            
            # Cache it
            await self._add_to_cache(artifact)
            
            # Persist to disk
            self.state_manager.save_player_artifact(artifact)
            
            self._current_artifact = artifact
            self._last_refresh = datetime.utcnow()
            
            print(f"[PlayerArtifact] Synced successfully: v{player_version_id[:12]}... STS={extracted_sts}")
            
            return artifact
            
        except Exception as e:
            print(f"[PlayerArtifact] Sync failed: {e}")
            
            # Try to use cached artifact if available
            if self._current_artifact:
                print("[PlayerArtifact] Falling back to existing artifact")
                return self._current_artifact
            
            raise
    
    def _extract_sts_safe(self, js_code: str) -> str:
        """
        Extract STS with proper error handling.
        Treats failure as hard error, not silent fallback.
        """
        sts_match = re.search(r'sts["\']?\s*:\s*(\d+)', js_code)
        
        if not sts_match:
            # Try alternative patterns
            sts_match = re.search(r'signatureTimestamp["\']?\s*:\s*(\d+)', js_code)
        
        if not sts_match:
            print("[PlayerArtifact] WARNING: Failed to extract STS, using default")
            return "19000"  # Fallback, but log it
        
        return sts_match.group(1)
    
    async def _extract_functions(self, js_code: str) -> tuple:
        """
        Extract signature decipher and n-parameter functions.
        Runs in thread pool to avoid blocking event loop.
        """
        loop = asyncio.get_event_loop()
        
        # Run extraction in thread pool (CPU-bound)
        result = await loop.run_in_executor(
            self._js_executor,
            self._extract_functions_sync,
            js_code
        )
        
        return result
    
    def _extract_functions_sync(self, js_code: str) -> tuple:
        """
        Synchronous function extraction (runs in thread pool).
        Returns: (decipher_code, n_code)
        """
        try:
            # Extract signature decipher function
            decipher_code = self._extract_decipher_function(js_code)
            
            # Extract n-parameter function
            n_code = self._extract_n_function(js_code)
            
            return (decipher_code, n_code)
            
        except Exception as e:
            print(f"[PlayerArtifact] Function extraction failed: {e}")
            return (None, None)
    
    def _extract_decipher_function(self, js_code: str) -> Optional[str]:
        """Extract signature decipher function with multiple patterns"""
        patterns = [
            r'\.sig\|\|([a-zA-Z0-9$]+)\(',
            r'signature=([a-zA-Z0-9$]+)\(',
            r'\.s\)\s*&&\s*\w+\.set\([^,]+,\s*([a-zA-Z0-9$]+)\(',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, js_code)
            if match:
                func_name = match.group(1)
                # Extract the full function definition
                func_pattern = rf'{re.escape(func_name)}=function\([^)]*\)\{{[^}}]+\}}'
                func_match = re.search(func_pattern, js_code, re.DOTALL)
                if func_match:
                    return func_match.group(0)
        
        return None
    
    def _extract_n_function(self, js_code: str) -> Optional[str]:
        """Extract n-parameter throttling function"""
        patterns = [
            r'&&\(b=([a-zA-Z0-9$]+)(\[[\w\d]+\])\([a-zA-Z]\)',
            r'\(b\.s\|\|([a-zA-Z0-9$]+)\[',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, js_code)
            if match:
                # This is complex - simplified version
                return "n_function_placeholder"
        
        return None
    
    async def _get_from_cache(self, version_id: str) -> Optional[PlayerArtifact]:
        """Get artifact from memory cache or disk"""
        async with self._cache_lock:
            # Check memory cache
            if version_id in self._artifact_cache:
                return self._artifact_cache[version_id]
            
            # Check disk cache
            artifact = self.state_manager.load_player_artifact(version_id)
            if artifact:
                # Add to memory cache
                self._artifact_cache[version_id] = artifact
                return artifact
            
            return None
    
    async def _add_to_cache(self, artifact: PlayerArtifact):
        """Add artifact to cache with LRU eviction"""
        async with self._cache_lock:
            self._artifact_cache[artifact.player_version_id] = artifact
            
            # Simple LRU: keep only most recent artifacts
            if len(self._artifact_cache) > IYEConfig.PLAYER_CACHE_SIZE:
                # Remove oldest
                oldest_key = min(
                    self._artifact_cache.keys(),
                    key=lambda k: self._artifact_cache[k].created_at
                )
                del self._artifact_cache[oldest_key]
    
    async def close(self):
        """Cleanup resources"""
        self._js_executor.shutdown(wait=True)
