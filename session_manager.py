"""
IYE Session Manager - Resilient session factory with identity preservation
Solves: "Long-lived sessions die, need recreation without losing identity"
"""
import asyncio
from typing import Optional, Dict
from curl_cffi.requests import AsyncSession
from config import IYEConfig
from gems import ExtractionGems, BotDefeatTechniques

class SessionFactory:
    """
    Session factory that can recreate sessions while preserving:
    - Logical headers
    - Cookie jar
    - TLS fingerprint
    - Proxy configuration
    
    Enables recovery from NAT rebinding, idle connection closes, etc.
    """
    
    def __init__(
        self,
        impersonate: str = "chrome120",
        proxy: Optional[str] = None,
        enable_mobile: bool = False
    ):
        self.impersonate = impersonate
        self.proxy = proxy
        self.enable_mobile = enable_mobile
        self.cookie_jar: Dict[str, str] = {}
        self.visitor_id: Optional[str] = None
        self.session_id: Optional[str] = None
        self._current_session: Optional[AsyncSession] = None
    
    async def create_session(self) -> AsyncSession:
        """
        Create a new session with all identity preservation.
        Can be called multiple times to recover from failures.
        """
        # Build base headers
        headers = self._build_headers()
        
        # Create session with curl_cffi for TLS fingerprinting
        session = AsyncSession(
            impersonate=self.impersonate,
            headers=headers,
            proxies={"http": self.proxy, "https": self.proxy} if self.proxy else None,
            timeout=IYEConfig.TOTAL_TIMEOUT
        )
        
        # Restore cookies if we have them
        if self.cookie_jar:
            for name, value in self.cookie_jar.items():
                session.cookies.set(name, value)
        
        # Age cookies on first creation
        if not self._current_session:
            await ExtractionGems.age_cookies(session)
            
            # Store identity markers
            self.visitor_id = ExtractionGems.generate_visitor_id()
            self.session_id = ExtractionGems.generate_session_id()
        
        self._current_session = session
        return session
    
    def _build_headers(self) -> Dict[str, str]:
        """
        Build complete header set with all anti-bot signals.
        """
        if self.enable_mobile:
            headers = ExtractionGems.get_mobile_headers()
        else:
            # Desktop headers with full consistency
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "DNT": "1",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1"
            }
            
            # Add client hints for consistency
            headers.update(ExtractionGems.build_client_hints())
            
            # Add ServiceWorker headers
            headers.update(ExtractionGems.inject_sw_headers())
        
        return headers
    
    async def get_session(self) -> AsyncSession:
        """
        Get current session, creating if needed.
        """
        if self._current_session is None:
            return await self.create_session()
        return self._current_session
    
    async def recreate_session(self):
        """
        Recreate session after failure.
        Preserves identity (cookies, visitor ID, etc.)
        """
        # Save cookie jar from old session
        if self._current_session:
            self.cookie_jar = dict(self._current_session.cookies)
            await self._current_session.close()
        
        # Create new session with preserved identity
        print("[Session] Recreating session with preserved identity...")
        return await self.create_session()
    
    async def rotate_tls_fingerprint(self, attempt: int):
        """
        Rotate TLS fingerprint on detection.
        Useful when one fingerprint gets flagged.
        """
        new_fingerprint = await BotDefeatTechniques.adaptive_tls_rotation(self, attempt)
        self.impersonate = new_fingerprint
        
        # Recreate session with new fingerprint
        return await self.recreate_session()
    
    def get_visitor_id(self) -> str:
        """Get persistent visitor ID for this session"""
        if not self.visitor_id:
            self.visitor_id = ExtractionGems.generate_visitor_id()
        return self.visitor_id
    
    def get_session_id(self) -> str:
        """Get session ID (changes per extraction batch)"""
        if not self.session_id:
            self.session_id = ExtractionGems.generate_session_id()
        return self.session_id
    
    async def close(self):
        """Clean shutdown"""
        if self._current_session:
            await self._current_session.close()
            self._current_session = None
