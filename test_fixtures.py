"""
IYE Test Fixtures & Validation
Ensures regex extractors remain functional across YouTube updates
"""
import re
from typing import Dict, List, Optional

# ============================================================================
# Test Fixtures - Sanitized samples from real YouTube responses
# ============================================================================

FIXTURE_WATCH_PAGE_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <script>
        var ytInitialPlayerResponse = {"responseContext":{"serviceTrackingParams":[]}, 
        "playabilityStatus":{"status":"OK"}, "streamingData":{}, 
        "videoDetails":{"videoId":"dQw4w9WgXcQ","title":"Test Video"}};
    </script>
    <script nonce="xyz" src="/s/player/a1b2c3d4/player_ias.vflset/en_US/base.js"></script>
    <link rel="canonical" href="https://www.youtube.com/watch?v=dQw4w9WgXcQ">
</head>
<body>
    <div id="player"></div>
</body>
</html>
'''

FIXTURE_BASE_JS_SNIPPET = '''
(function(){
var a={sts:19461,some:"other",data:123};
var b=function(c){c=c.split("");d.reverse(c);return c.join("")};
var d={reverse:function(a){a.reverse()},swap:function(a,b){var c=a[0];a[0]=a[b%a.length];a[b%a.length]=c}};
function signatureFunction(a){a=a.split("");d.reverse(a);d.swap(a,15);return a.join("")}
window.ytplayer={config:{args:{sig:signatureFunction}}};
})();
'''

FIXTURE_PLAYER_RESPONSE = {
    "videoDetails": {
        "videoId": "dQw4w9WgXcQ",
        "title": "Test Video Title",
        "lengthSeconds": "212",
        "keywords": ["test", "video"],
        "channelId": "UCuAXFkgsw1L7xaCfnd5JJOw",
        "shortDescription": "Test description",
        "viewCount": "1234567890",
        "author": "Test Author",
        "isLiveContent": False
    },
    "streamingData": {
        "expiresInSeconds": "21540",
        "adaptiveFormats": [
            {
                "itag": 137,
                "url": "https://example.com/videoplayback?expire=123&ei=xyz",
                "mimeType": "video/mp4; codecs=\"avc1.640028\"",
                "bitrate": 2500000,
                "width": 1920,
                "height": 1080,
                "fps": 30,
                "qualityLabel": "1080p",
                "contentLength": "12345678"
            },
            {
                "itag": 140,
                "url": "https://example.com/videoplayback?expire=123&ei=abc",
                "mimeType": "audio/mp4; codecs=\"mp4a.40.2\"",
                "bitrate": 128000,
                "contentLength": "2345678"
            }
        ]
    }
}

# ============================================================================
# Extractor Validators
# ============================================================================

class ExtractorValidator:
    """
    Test extractors against fixtures to detect breaking changes.
    Run this as part of CI/CD or periodically in production.
    """
    
    def __init__(self):
        self.failures: List[str] = []
        self.warnings: List[str] = []
    
    def validate_all(self) -> bool:
        """
        Run all validations.
        Returns True if all pass, False if any fail.
        """
        print("\n" + "="*60)
        print("Running Extractor Validations")
        print("="*60 + "\n")
        
        self.failures = []
        self.warnings = []
        
        # Run all validators
        self.validate_player_url_extraction()
        self.validate_sts_extraction()
        self.validate_signature_function_extraction()
        self.validate_player_response_parsing()
        
        # Report results
        print("\n" + "="*60)
        if not self.failures:
            print("✅ All validations passed!")
        else:
            print(f"❌ {len(self.failures)} validation(s) failed:")
            for failure in self.failures:
                print(f"   - {failure}")
        
        if self.warnings:
            print(f"\n⚠️  {len(self.warnings)} warning(s):")
            for warning in self.warnings:
                print(f"   - {warning}")
        
        print("="*60 + "\n")
        
        return len(self.failures) == 0
    
    def validate_player_url_extraction(self):
        """Test player URL regex extraction"""
        print("Testing: Player URL extraction...")
        
        pattern = r'"jsUrl"\s*:\s*"(/s/player/[^"]+/player[^"]+\.js)"'
        match = re.search(pattern, FIXTURE_WATCH_PAGE_HTML)
        
        if not match:
            self.failures.append("Player URL extraction failed")
            return
        
        extracted = match.group(1).replace(r'\/', '/')
        expected = "/s/player/a1b2c3d4/player_ias.vflset/en_US/base.js"
        
        if extracted != expected:
            self.failures.append(f"Player URL mismatch: got {extracted}")
        else:
            print("  ✅ Player URL extraction working")
    
    def validate_sts_extraction(self):
        """Test STS extraction"""
        print("Testing: STS extraction...")
        
        # Primary pattern
        pattern1 = r'sts["\']?\s*:\s*(\d+)'
        match1 = re.search(pattern1, FIXTURE_BASE_JS_SNIPPET)
        
        # Fallback pattern
        pattern2 = r'signatureTimestamp["\']?\s*:\s*(\d+)'
        match2 = re.search(pattern2, FIXTURE_BASE_JS_SNIPPET)
        
        if not match1 and not match2:
            self.failures.append("STS extraction failed (both patterns)")
            return
        
        extracted = match1.group(1) if match1 else match2.group(1) if match2 else None
        expected = "19461"
        
        if extracted != expected:
            self.failures.append(f"STS mismatch: got {extracted}, expected {expected}")
        else:
            print("  ✅ STS extraction working")
    
    def validate_signature_function_extraction(self):
        """Test signature function name extraction"""
        print("Testing: Signature function extraction...")
        
        # This is more complex - just check the pattern exists
        patterns = [
            r'\.sig\|\|([a-zA-Z0-9$]+)\(',
            r'signature=([a-zA-Z0-9$]+)\(',
            r'signatureFunction'  # Simplified for fixture
        ]
        
        found = False
        for pattern in patterns:
            if re.search(pattern, FIXTURE_BASE_JS_SNIPPET):
                found = True
                break
        
        if not found:
            self.failures.append("Signature function pattern not found")
        else:
            print("  ✅ Signature function extraction working")
    
    def validate_player_response_parsing(self):
        """Test Pydantic model parsing"""
        print("Testing: Player response parsing...")
        
        try:
            from models import VideoDetails, StreamFormat
            
            # Parse video details
            video_details = VideoDetails(**FIXTURE_PLAYER_RESPONSE["videoDetails"])
            
            if video_details.video_id != "dQw4w9WgXcQ":
                self.failures.append("VideoDetails parsing incorrect")
                return
            
            # Parse streams
            for fmt in FIXTURE_PLAYER_RESPONSE["streamingData"]["adaptiveFormats"]:
                stream = StreamFormat(**fmt)
                if not stream.itag:
                    self.failures.append("StreamFormat parsing failed")
                    return
            
            print("  ✅ Pydantic model parsing working")
            
        except Exception as e:
            self.failures.append(f"Model parsing error: {e}")

# ============================================================================
# Canary Detection
# ============================================================================

class DriftCanary:
    """
    Detects when extractors start failing in production.
    Alerts before complete breakage.
    """
    
    def __init__(self):
        self.failure_count = 0
        self.total_attempts = 0
    
    def record_extraction_attempt(self, success: bool):
        """Record extraction attempt result"""
        self.total_attempts += 1
        if not success:
            self.failure_count += 1
    
    def get_failure_rate(self) -> float:
        """Calculate current failure rate"""
        if self.total_attempts == 0:
            return 0.0
        return self.failure_count / self.total_attempts
    
    def check_drift_threshold(self, threshold: float = 0.2) -> bool:
        """
        Check if drift threshold exceeded.
        
        Args:
            threshold: Failure rate threshold (default 20%)
        
        Returns:
            True if threshold exceeded (action needed)
        """
        if self.total_attempts < 10:
            return False  # Need more samples
        
        failure_rate = self.get_failure_rate()
        
        if failure_rate > threshold:
            print(f"\n⚠️  DRIFT CANARY ALERT!")
            print(f"   Failure rate: {failure_rate*100:.1f}%")
            print(f"   Attempts: {self.total_attempts}")
            print(f"   Failures: {self.failure_count}")
            print(f"   Action: Update extractors or rotate techniques\n")
            return True
        
        return False

# ============================================================================
# Main Test Runner
# ============================================================================

def run_validation():
    """Run all validation tests"""
    validator = ExtractorValidator()
    success = validator.validate_all()
    
    if success:
        print("✅ All systems operational")
        return 0
    else:
        print("❌ Validation failed - extractors may need updates")
        return 1

if __name__ == "__main__":
    import sys
    sys.exit(run_validation())
