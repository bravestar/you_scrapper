"""
IYE Usage Examples - Real-world scenarios
Complete examples for common use cases
"""
import asyncio
from main import IYEOrchestrator

# ============================================================================
# Example 1: Simple Extraction
# ============================================================================

async def example_1_simple():
    """
    Most basic usage - extract and download a single video
    """
    print("\n=== Example 1: Simple Extraction ===\n")
    
    iye = IYEOrchestrator(output_dir="./downloads")
    
    try:
        filepath = await iye.extract_and_download(
            video_id="dQw4w9WgXcQ",
            prefer_codec="vp9"  # VP9 or H264
        )
        print(f"✅ Success: {filepath}")
        
    except Exception as e:
        print(f"❌ Failed: {e}")
    
    finally:
        await iye.close()

# ============================================================================
# Example 2: Metadata Only (No Download)
# ============================================================================

async def example_2_metadata_only():
    """
    Extract metadata without downloading - useful for:
    - Preview before download
    - Bulk metadata collection
    - Checking availability
    """
    print("\n=== Example 2: Metadata Only ===\n")
    
    iye = IYEOrchestrator()
    
    try:
        result = await iye.extract_video("dQw4w9WgXcQ")
        
        # Access all metadata
        print(f"📹 Title: {result.metadata.title}")
        print(f"👤 Author: {result.metadata.author}")
        print(f"⏱️  Duration: {result.metadata.length_seconds}s")
        print(f"👁️  Views: {result.metadata.view_count:,}")
        print(f"🎬 Streams: {len(result.streams)}")
        print(f"🔒 Detection Risk: {result.telemetry.detection_risk.value}")
        
        # List available qualities
        print("\n📊 Available Streams:")
        for stream in result.streams[:10]:
            quality = f"{stream.height}p" if stream.height else "audio"
            codec = "VP9" if "vp9" in stream.mime_type else "H264"
            bitrate_mbps = stream.bitrate / 1_000_000
            print(f"  • {quality:6} | {codec:4} | {bitrate_mbps:.1f} Mbps")
        
    finally:
        await iye.close()

# ============================================================================
# Example 3: Batch Processing
# ============================================================================

async def example_3_batch_processing():
    """
    Process multiple videos concurrently
    """
    print("\n=== Example 3: Batch Processing ===\n")
    
    iye = IYEOrchestrator()
    
    # List of videos to extract
    playlist = [
        "dQw4w9WgXcQ",  # Never Gonna Give You Up
        "9bZkp7q19f0",  # Gangnam Style
        "kJQP7kiw5Fk",  # Despacito
    ]
    
    try:
        results = await iye.extract_multiple(
            video_ids=playlist,
            max_concurrent=2  # Process 2 at a time
        )
        
        print(f"\n✅ Extracted {len(results)} videos:")
        for result in results:
            if result:
                print(f"  • {result.metadata.title[:50]}...")
        
    finally:
        await iye.close()

# ============================================================================
# Example 4: Network Failure Recovery
# ============================================================================

async def example_4_network_resilience():
    """
    Demonstrate automatic resume after network failure
    """
    print("\n=== Example 4: Network Resilience ===\n")
    
    iye = IYEOrchestrator(output_dir="./downloads")
    
    try:
        print("Starting download (you can kill this and restart)...")
        
        filepath = await iye.extract_and_download("dQw4w9WgXcQ")
        print(f"✅ Completed: {filepath}")
        
    except KeyboardInterrupt:
        print("\n⚠️  Interrupted! State saved automatically.")
        print("Run this again to resume from where you left off.")
    
    except Exception as e:
        print(f"❌ Failed: {e}")
        print("State saved - you can resume later")
    
    finally:
        await iye.close()

# ============================================================================
# Example 5: Resume Incomplete Downloads
# ============================================================================

async def example_5_resume():
    """
    Resume any incomplete downloads from previous runs
    """
    print("\n=== Example 5: Resume Incomplete ===\n")
    
    iye = IYEOrchestrator()
    
    try:
        await iye.resume_incomplete_jobs()
        
    finally:
        await iye.close()

# ============================================================================
# Example 6: High-Risk Detection Handling
# ============================================================================

async def example_6_detection_handling():
    """
    Handle high detection risk scenarios
    """
    print("\n=== Example 6: Detection Risk Handling ===\n")
    
    iye = IYEOrchestrator()
    
    try:
        result = await iye.extract_video("dQw4w9WgXcQ")
        
        # Check detection risk
        risk_score = result.telemetry.calculate_risk_score()
        
        if risk_score > 0.7:
            print(f"⚠️  HIGH RISK DETECTED: {risk_score:.2f}")
            print("Recommended actions:")
            print("  1. Switch to residential proxy")
            print("  2. Rotate TLS fingerprint")
            print("  3. Increase delays between requests")
            
            # Rotate TLS fingerprint
            await iye.session_factory.rotate_tls_fingerprint(attempt=1)
            print("✅ TLS fingerprint rotated")
        
        else:
            print(f"✅ Risk acceptable: {risk_score:.2f}")
        
    finally:
        await iye.close()

# ============================================================================
# Example 7: Custom Quality Selection
# ============================================================================

async def example_7_quality_selection():
    """
    Download specific quality instead of best available
    """
    print("\n=== Example 7: Quality Selection ===\n")
    
    iye = IYEOrchestrator(output_dir="./downloads")
    
    try:
        # Extract metadata first
        result = await iye.extract_video("dQw4w9WgXcQ")
        
        # Find 720p stream
        target_streams = [
            s for s in result.streams 
            if s.height == 720 and "video" in s.mime_type
        ]
        
        if target_streams:
            # Sort by bitrate, get best 720p
            best_720p = max(target_streams, key=lambda s: s.bitrate)
            
            print(f"Selected: 720p @ {best_720p.bitrate / 1_000_000:.1f} Mbps")
            
            # Download this specific stream
            import uuid
            job_id = f"{result.metadata.video_id}_{uuid.uuid4().hex[:8]}"
            
            filepath = await iye.downloader.download_stream(
                job_id=job_id,
                stream=best_720p,
                target_filename=f"./downloads/{result.metadata.video_id}_720p.mp4",
                video_id=result.metadata.video_id
            )
            
            print(f"✅ Downloaded: {filepath}")
        
        else:
            print("❌ No 720p streams available")
        
    finally:
        await iye.close()

# ============================================================================
# Example 8: Using Proxy
# ============================================================================

async def example_8_with_proxy():
    """
    Use a proxy for extraction (residential or datacenter)
    """
    print("\n=== Example 8: Using Proxy ===\n")
    
    # Configure proxy
    iye = IYEOrchestrator(
        proxy="http://username:password@proxy.example.com:8080"
    )
    
    try:
        result = await iye.extract_video("dQw4w9WgXcQ")
        print(f"✅ Extracted via proxy: {result.metadata.title}")
        
    finally:
        await iye.close()

# ============================================================================
# Example 9: Mobile Mode
# ============================================================================

async def example_9_mobile_mode():
    """
    Use mobile web (MWEB) impersonation for lower detection
    """
    print("\n=== Example 9: Mobile Mode ===\n")
    
    iye = IYEOrchestrator(enable_mobile=True)
    
    try:
        result = await iye.extract_video("dQw4w9WgXcQ")
        print(f"✅ Extracted (MWEB): {result.metadata.title}")
        print(f"   Detection Risk: {result.telemetry.detection_risk.value}")
        
    finally:
        await iye.close()

# ============================================================================
# Main Menu
# ============================================================================

async def main():
    """
    Interactive example selector
    """
    examples = {
        "1": ("Simple Extraction", example_1_simple),
        "2": ("Metadata Only", example_2_metadata_only),
        "3": ("Batch Processing", example_3_batch_processing),
        "4": ("Network Resilience", example_4_network_resilience),
        "5": ("Resume Incomplete", example_5_resume),
        "6": ("Detection Handling", example_6_detection_handling),
        "7": ("Quality Selection", example_7_quality_selection),
        "8": ("Using Proxy", example_8_with_proxy),
        "9": ("Mobile Mode", example_9_mobile_mode),
    }
    
    print("\n" + "="*60)
    print("IYE Usage Examples")
    print("="*60)
    
    for key, (name, _) in examples.items():
        print(f"  {key}. {name}")
    
    print("\nEnter example number (or press Enter for Example 2): ", end="")
    
    # For automation, just run example 2
    choice = "2"
    
    if choice in examples:
        _, func = examples[choice]
        await func()
    else:
        print("\n❌ Invalid choice, running Example 2...")
        await example_2_metadata_only()

if __name__ == "__main__":
    asyncio.run(main())
