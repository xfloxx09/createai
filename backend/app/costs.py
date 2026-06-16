COST_PER_SCRAPE = {
    "instagram": 0.002,
    "tiktok": 0.0,
    "youtube": 0.0,
    "facebook": 0.002,
}

COST_PER_GENERATE = {
    "pexels_stock": 0.0,
    "whisper_transcribe": 0.0,
    "ffmpeg_render": 0.0,
}

COST_PER_UPLOAD = {
    "instagram": 0.0,
    "tiktok": 0.0,
    "youtube": 0.0,
    "facebook": 0.0,
}

PROVIDERS = {
    "scrape": {
        "instagram": {"name": "Apify Instagram Scraper", "cost": "$0.002/video", "tier": "Paid", "link": "https://apify.com/apify/instagram-scraper", "notes": "Free $5 monthly credit on new accounts"},
        "tiktok": {"name": "TikTokApi (community)", "cost": "Free", "tier": "Free", "link": "https://github.com/davidteather/TikTokApi", "notes": "Unofficial API, may break"},
        "youtube": {"name": "yt-dlp + YouTube Data API", "cost": "Free", "tier": "Free", "link": "https://github.com/yt-dlp/yt-dlp", "notes": "10,000 quota units/day free"},
        "facebook": {"name": "Apify Facebook Scraper", "cost": "$0.002/video", "tier": "Paid", "link": "https://apify.com/apify/facebook-scraper", "notes": "Free $5 monthly credit on new accounts"},
    },
    "generate": {
        "stock_video": {"name": "Pexels API", "cost": "Free", "tier": "Free", "link": "https://www.pexels.com/api/", "notes": "200 requests/hour, 20,000/month"},
        "transcription": {"name": "OpenAI Whisper (local)", "cost": "Free", "tier": "Free", "link": "https://github.com/openai/whisper", "notes": "Runs locally on CPU/GPU, no API cost"},
        "video_compositing": {"name": "MoviePy + FFmpeg", "cost": "Free", "tier": "Free", "link": "https://zulko.github.io/moviepy/", "notes": "Open-source, runs locally"},
    },
    "upload": {
        "instagram": {"name": "Meta Graph API", "cost": "Free", "tier": "Free", "link": "https://developers.facebook.com/docs/instagram-api/", "notes": "Requires Facebook Page + Instagram Business"},
        "tiktok": {"name": "upload-post.com", "cost": "Free tier", "tier": "Freemium", "link": "https://upload-post.com", "notes": "Free tier available, paid for high volume"},
        "youtube": {"name": "YouTube Data API v3", "cost": "Free", "tier": "Free", "link": "https://developers.google.com/youtube/v3", "notes": "10,000 quota units/day free"},
        "facebook": {"name": "Meta Graph API", "cost": "Free", "tier": "Free", "link": "https://developers.facebook.com/docs/video-api/", "notes": "Requires Facebook Page"},
    },
}


def estimate_scrape_cost(platforms: list[str], count: int) -> dict:
    total = 0.0
    breakdown = {}
    for p in platforms:
        per = COST_PER_SCRAPE.get(p, 0)
        cost = per * count
        total += cost
        breakdown[p] = {"per_video": per, "count": count, "total": round(cost, 6)}
    return {"total": round(total, 6), "breakdown": breakdown}


def estimate_generate_cost() -> dict:
    total = sum(COST_PER_GENERATE.values())
    return {"total": total, "breakdown": {k: v for k, v in COST_PER_GENERATE.items()}}


def estimate_upload_cost(platforms: list[str]) -> dict:
    total = 0.0
    breakdown = {}
    for p in platforms:
        cost = COST_PER_UPLOAD.get(p, 0)
        total += cost
        breakdown[p] = cost
    return {"total": total, "breakdown": breakdown}


def estimate_full_pipeline(platforms: list[str], count: int) -> dict:
    scrape = estimate_scrape_cost(platforms, count)
    generate = estimate_generate_cost()
    upload = estimate_upload_cost(platforms)
    total = round(scrape["total"] + generate["total"] + upload["total"], 6)
    return {
        "total_per_batch": total,
        "total_per_video": round(total / max(count, 1), 6),
        "scrape": scrape,
        "generate": generate,
        "upload": upload,
    }
