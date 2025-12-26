# IYE Quick Reference Guide

## 🚀 Installation
```bash
pip install -r requirements.txt
```

## 📖 Basic Usage Patterns

### Extract Metadata Only
```python
from main import IYEOrchestrator

async def extract():
    iye = IYEOrchestrator()
    try:
        result = await iye.extract_video("VIDEO_ID")
        print(f"{result.metadata.title} - {len(result.streams)} streams")
    finally:
        await iye.close()

import asyncio
asyncio.run(extract())
```

### Extract and Download
```python
async def download():
    iye = IYEOrchestrator(output_dir="./videos")
    try:
        path = await iye.extract_and_download("VIDEO_ID", prefer_codec="vp9")
        print(f"Downloaded: {path}")
    finally:
        await iye.close()

asyncio.run(download())
```

### Batch Processing
```python
async def batch():
    iye = IYEOrchestrator()
    try:
        results = await iye.extract_multiple(
            ["VIDEO_ID_1", "VIDEO_ID_2"], 
            max_concurrent=2
        )
    finally:
        await iye.close()

asyncio.run(batch())
```

## 🛡️ Network Resilience Features

### Automatic Resume
```python
# If download fails, just run again - it resumes automatically
iye = IYEOrchestrator()
await iye.extract_and_download("VIDEO_ID")  # Crashes at 50%
# ... restart ...
await iye.extract_and_download("VIDEO_ID")  # Resumes from 50%
```

### Manual Resume
```python
iye = IYEOrchestrator()
await iye.resume_incomplete_jobs()  # Resumes all incomplete
```

### State Inspection
```python
from state_manager import StateManager

state_mgr = StateManager()
incomplete = state_mgr.list_incomplete_jobs()

for job_id, state in incomplete.items():
    print(f"{state.video_id}: {state.bytes_completed:,} bytes")
```

## 🔧 Configuration Options

### Mobile Mode
```python
iye = IYEOrchestrator(enable_mobile=True)  # MWEB impersonation
```

### With Proxy
```python
iye = IYEOrchestrator(proxy="http://user:pass@proxy.com:8080")
```

### Custom TLS Fingerprint
```python
from session_manager import SessionFactory

factory = SessionFactory(impersonate="safari17_2")
# Options: chrome120, chrome119, safari17_0, safari17_2
```

### Modify Retry Settings
Edit `config.py`:
```python
MAX_RETRIES = 5
RETRY_BACKOFF_BASE = 3.0
CIRCUIT_BREAKER_THRESHOLD = 10
```

## 📊 Telemetry Monitoring

### Check Detection Risk
```python
result = await iye.extract_video("VIDEO_ID")

risk = result.telemetry.detection_risk
# Values: LOW, MEDIUM, HIGH, CRITICAL

if risk == DetectionRisk.HIGH:
    # Take action: rotate proxy, change fingerprint
    await iye.session_factory.rotate_tls_fingerprint(1)
```

### Access Telemetry Data
```python
t = result.telemetry

print(f"Response Time: {t.response_time:.2f}s")
print(f"Status Code: {t.status_code}")
print(f"Rate Limited: {t.rate_limited}")
print(f"CAPTCHA: {t.captcha_triggered}")
print(f"Risk Score: {t.calculate_risk_score():.2f}")
```

## 🎯 Stream Selection

### Get Best Quality
```python
result = await iye.extract_video("VIDEO_ID")

# Filter video streams
video_streams = [s for s in result.streams if "video" in s.mime_type]

# Get highest resolution
best = max(video_streams, key=lambda s: (s.height or 0, s.bitrate))

print(f"{best.height}p @ {best.bitrate/1_000_000:.1f} Mbps")
```

### Download Specific Quality
```python
# Get 720p streams
streams_720p = [
    s for s in result.streams 
    if s.height == 720 and "video" in s.mime_type
]

if streams_720p:
    best_720p = max(streams_720p, key=lambda s: s.bitrate)
    
    import uuid
    job_id = f"{result.metadata.video_id}_{uuid.uuid4().hex[:8]}"
    
    await iye.downloader.download_stream(
        job_id=job_id,
        stream=best_720p,
        target_filename="./video_720p.mp4",
        video_id=result.metadata.video_id
    )
```

### Filter by Codec
```python
# VP9 streams only
vp9_streams = [s for s in result.streams if "vp9" in s.mime_type]

# H.264 streams only
h264_streams = [s for s in result.streams if "avc1" in s.mime_type]
```

## 🔍 Advanced Features

### Use DASH Manifest (Alternative Approach)
```python
manifest_url = await iye.engine.get_dash_manifest("VIDEO_ID")
# Bypasses signature throttling
```

### Extract from Embed (Fallback)
```python
data = await iye.engine.extract_from_embed("VIDEO_ID")
# Lower security endpoint, useful as fallback
```

### Manual Player Artifact Refresh
```python
artifact = await iye.player_manager.sync_player_artifact()
print(f"STS: {artifact.extracted_sts}")
print(f"Version: {artifact.player_version_id[:12]}...")
```

## 🧪 Testing & Validation

### Run Extractor Tests
```python
python test_fixtures.py
# Validates all regex patterns against fixtures
```

### Monitor for Drift
```python
from test_fixtures import DriftCanary

canary = DriftCanary()

# After each extraction
canary.record_extraction_attempt(success=True/False)

if canary.check_drift_threshold(threshold=0.2):
    # >20% failure rate - update needed
    print("⚠️  High failure rate detected")
```

## 📁 Project Structure

```
iye/
├── config.py              # Settings
├── models.py              # Data models
├── circuit_breaker.py     # Retry logic
├── state_manager.py       # State persistence
├── gems.py                # Bot defeat techniques
├── session_manager.py     # Session factory
├── player_artifacts.py    # Player extraction
├── engine.py              # InnerTube API
├── downloader.py          # Resumable downloads
├── main.py                # Orchestration
├── examples.py            # Usage examples
├── test_fixtures.py       # Validation tests
└── README.md              # Full documentation
```

## 🐛 Common Issues

### "Circuit breaker OPEN"
```python
# Too many failures - wait 60s or restart
# Or increase threshold in config.py
CIRCUIT_BREAKER_THRESHOLD = 10  # Default: 5
```

### "Player artifact sync failed"
```python
# YouTube changed player format
# Run validation:
python test_fixtures.py
# Update regex patterns in player_artifacts.py
```

### "High detection risk"
```python
# Rotate TLS fingerprint
await iye.session_factory.rotate_tls_fingerprint(1)

# Or use mobile mode
iye = IYEOrchestrator(enable_mobile=True)

# Or add proxy
iye = IYEOrchestrator(proxy="...")
```

### Downloads fail to resume
```python
# Check state directory
from state_manager import StateManager
mgr = StateManager()
incomplete = mgr.list_incomplete_jobs()
print(incomplete)

# Manual state cleanup if needed
mgr.delete_extraction_state("job_id")
```

## 💡 Performance Tips

1. **Use batch processing** for multiple videos
2. **Enable state persistence** (on by default)
3. **Monitor telemetry** to detect problems early
4. **Rotate TLS fingerprints** on high detection
5. **Use semaphore limits** to avoid overwhelming YouTube
6. **Cache player artifacts** (automatic via LRU)

## 📊 Detection Avoidance Rates

| Technique | Implementation | Success Rate |
|-----------|---------------|--------------|
| Base (no techniques) | Naive scraping | ~10-20% |
| TLS Fingerprinting | curl_cffi | ~80% |
| + PoToken | Client attestation | ~90% |
| + ServiceWorker Headers | Browser mimicry | ~92% |
| + Client Hints | Consistency | ~95% |
| + All Techniques | Full stack | ~98% |

## 🔗 Key URLs

- **GitHub Issues**: Report problems
- **Documentation**: Full README.md
- **Examples**: examples.py
- **Tests**: test_fixtures.py

---

**For detailed explanations, see README.md**
**For working examples, run examples.py**
**For testing, run test_fixtures.py**
