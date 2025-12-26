"""
Test script to scrape a single YouTube video and save results to JSON
"""
import asyncio
import json
from main import IYEOrchestrator

async def scrape_video():
    """Scrape a single video and save results to JSON"""

    # Extract video ID from URL
    video_id = "WLxPmoO4HvM"

    print(f"\n{'='*60}")
    print(f"Starting scrape for video: {video_id}")
    print(f"{'='*60}\n")

    # Initialize orchestrator
    iye = IYEOrchestrator()

    try:
        # Extract video data (metadata + streams)
        result = await iye.extract_video(video_id)

        # Convert to dict for JSON serialization
        result_dict = {
            "video_id": video_id,
            "metadata": {
                "title": result.metadata.title,
                "author": result.metadata.author,
                "channel_id": result.metadata.channel_id,
                "duration_seconds": result.metadata.length_seconds,
                "view_count": result.metadata.view_count,
                "keywords": result.metadata.keywords,
                "description": result.metadata.short_description,
                "is_live": result.metadata.is_live_content
            },
            "streams": [
                {
                    "itag": stream.itag,
                    "mime_type": stream.mime_type,
                    "quality": stream.quality,
                    "bitrate": stream.bitrate,
                    "width": stream.width,
                    "height": stream.height,
                    "fps": stream.fps,
                    "has_video": "video" in stream.mime_type if stream.mime_type else False,
                    "has_audio": "audio" in stream.mime_type if stream.mime_type else False,
                    "content_length": stream.content_length
                }
                for stream in result.streams
            ],
            "extraction_info": {
                "sts_version": result.sts,
                "player_version_id": result.player_version_id,
                "detection_risk": result.telemetry.detection_risk.value,
                "response_time": result.telemetry.response_time,
                "extracted_at": result.extracted_at.isoformat()
            }
        }

        # Save to JSON file
        output_file = "test_results.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result_dict, f, indent=2, ensure_ascii=False)

        print(f"\n{'='*60}")
        print(f"✅ SUCCESS!")
        print(f"{'='*60}")
        print(f"Results saved to: {output_file}")
        print(f"\nVideo Info:")
        print(f"  Title: {result.metadata.title}")
        print(f"  Author: {result.metadata.author}")
        print(f"  Duration: {result.metadata.length_seconds}s")
        print(f"  Views: {result.metadata.view_count:,}")
        print(f"  Streams found: {len(result.streams)}")
        print(f"  Detection Risk: {result.telemetry.detection_risk.value}")
        print(f"{'='*60}\n")

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

    finally:
        await iye.close()

if __name__ == "__main__":
    asyncio.run(scrape_video())
