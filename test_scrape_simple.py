"""
Simplified test script using basic requests library
"""
import json
import requests

def scrape_video_simple():
    """Simple scrape using basic requests library"""

    video_id = "WLxPmoO4HvM"

    print(f"\n{'='*60}")
    print(f"Testing basic connectivity and scraping")
    print(f"Video ID: {video_id}")
    print(f"{'='*60}\n")

    try:
        # Try to fetch YouTube page directly
        print("[1] Testing basic connectivity to YouTube...")
        url = f"https://www.youtube.com/watch?v={video_id}"

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

        response = requests.get(url, headers=headers, timeout=30)

        print(f"    Status Code: {response.status_code}")
        print(f"    Content Length: {len(response.text)} bytes")

        if response.status_code == 200:
            print("    ✓ Successfully connected to YouTube")

            # Try to extract basic info from HTML
            import re

            # Extract title
            title_match = re.search(r'"title":"([^"]+)"', response.text)
            title = title_match.group(1) if title_match else "Unknown"

            # Extract author
            author_match = re.search(r'"author":"([^"]+)"', response.text)
            author = author_match.group(1) if author_match else "Unknown"

            # Extract view count
            views_match = re.search(r'"viewCount":"(\d+)"', response.text)
            views = int(views_match.group(1)) if views_match else 0

            result = {
                "video_id": video_id,
                "url": url,
                "title": title,
                "author": author,
                "view_count": views,
                "scrape_method": "basic_html_extraction",
                "status": "success"
            }

            # Save to JSON
            with open("test_results.json", 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)

            print(f"\n{'='*60}")
            print(f"✅ SUCCESS!")
            print(f"{'='*60}")
            print(f"Results saved to: test_results.json")
            print(f"\nVideo Info:")
            print(f"  Title: {title}")
            print(f"  Author: {author}")
            print(f"  Views: {views:,}")
            print(f"{'='*60}\n")

        else:
            print(f"    ✗ Failed with status code: {response.status_code}")

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        print("\nThis appears to be a network connectivity issue.")
        print("The environment may be blocking outbound HTTPS connections to YouTube.")

        # Save error info
        error_result = {
            "video_id": video_id,
            "url": f"https://www.youtube.com/watch?v={video_id}",
            "status": "error",
            "error": str(e),
            "note": "Network connectivity blocked - scraper cannot reach YouTube"
        }

        with open("test_results.json", 'w', encoding='utf-8') as f:
            json.dump(error_result, f, indent=2, ensure_ascii=False)

        print("Error details saved to test_results.json")

if __name__ == "__main__":
    scrape_video_simple()
