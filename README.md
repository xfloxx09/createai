# CreateAI — Short-Form Video Mass Production MVP

Mass-produce short-form videos for **Instagram Reels**, **TikTok**, **YouTube Shorts**, and **Facebook Reels** by scraping trending content, scoring virality, generating new videos from winning patterns, and publishing them — all from one Docker Compose stack.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Frontend (React + Tailwind + Vite)     :80             │
│  Dashboard │ Generate │ Schedule │ Upload Log           │
└──────────────────────┬──────────────────────────────────┘
                       │ HTTP /api/*
┌──────────────────────▼──────────────────────────────────┐
│  Backend (FastAPI + OpenAPI)           :8000             │
│  ┌────────┐ ┌──────────┐ ┌────────┐ ┌───────────────┐  │
│  │Scrapers│ │ Scoring  │ │Generate│ │ Upload        │  │
│  │ IG   │ │ Engine   │ │Pipeline│ │ Manager       │  │
│  │ TT    │ │ Virality │ │FFmpeg  │ │ Meta Graph    │  │
│  │ YT    │ │ Score    │ │MoviePy │ │ YouTube Data  │  │
│  │ FB    │ │ 0-100    │ │Whisper │ │ Upload-Post   │  │
│  └────────┘ └──────────┘ └────────┘ └───────────────┘  │
└────────┬─────────────┬──────────────┬───────────────────┘
         │             │              │
    ┌────▼────┐  ┌─────▼─────┐  ┌────▼────┐
    │PostgreSQL│  │   Redis   │  │  Temp   │
    │ 16      │  │   7       │  │  Volume │
    └─────────┘  └───────────┘  └─────────┘
```

## Quick Start

```bash
# 1. Clone the repo
git clone https://github.com/xfloxx09/createai.git
cd createai

# 2. Copy and fill in environment variables
cp .env.example .env
# Edit .env with your API keys (see below)

# 3. Start everything
docker-compose up --build
```

Access the app:
- **Frontend**: http://localhost
- **Backend API**: http://localhost:8000
- **OpenAPI Docs**: http://localhost:8000/docs
- **Celery Flower** (optional): Add `-p 5555:5555` and run `celery -A app.scheduler.tasks.celery_app flower`

## API Key Setup Guide

### 1. Apify Token (required for Instagram & Facebook scrapers)

Cost: ~$0.002/video. New accounts get $5 free credit (~2,500 videos).

1. Go to https://console.apify.com/signup and create an account
2. Go to https://console.apify.com/settings/integrations
3. Copy your **API Token**
4. Set `APIFY_TOKEN=your_token` in `.env`

Actors used:
- Instagram: `vulnv/instagram-reels-scraper` (~$2/1k results)
- Facebook: `scrapers-hub/facebook-reels-scraper` (~$2/1k results)

**Fallback free tier**: YouTube and TikTok scrapers are free (no Apify needed).

### 2. Pexels API Key (required for stock video clips)

**Cost: Free.** 200 req/hour, 20,000 req/month.

1. Go to https://www.pexels.com/api/
2. Sign up and request a free API key (instant)
3. Set `PEXELS_API_KEY=your_key` in `.env`

### 3. Meta Graph API (Instagram & Facebook Reels publishing)

**Cost: Free.** Requires an Instagram Business/Creator account.

**Step-by-step:**

1. **Create a Meta Developer App:**
   - Go to https://developers.facebook.com/
   - Create a new app → **Business** type
   - Add **Instagram Graph API** + **Facebook Login** products

2. **Get a Page Access Token (never expires):**
   - Short-lived token (~1hr): https://developers.facebook.com/tools/explorer/
   - Exchange for 60-day token:
     ```bash
     curl "https://graph.facebook.com/v21.0/oauth/access_token?grant_type=fb_exchange_token&client_id=APP_ID&client_secret=APP_SECRET&fb_exchange_token=SHORT_LIVED_TOKEN"
     ```
   - Get permanent Page Token (never expires):
     ```bash
     curl "https://graph.facebook.com/v21.0/PAGE_ID?fields=access_token&access_token=LONG_LIVED_USER_TOKEN"
     ```

3. **Find your Instagram Business Account ID:**
   ```bash
   curl "https://graph.facebook.com/v21.0/me/accounts?access_token=PAGE_TOKEN"
   # Then:
   curl "https://graph.facebook.com/v21.0/PAGE_ID?fields=instagram_business_account&access_token=PAGE_TOKEN"
   ```

4. Set in `.env`:
   ```
   META_APP_ID=your_app_id
   META_APP_SECRET=your_app_secret
   META_PAGE_ACCESS_TOKEN=your_page_token
   META_IG_USER_ID=your_ig_business_id
   ```

### 4. YouTube Data API v3 (YouTube Shorts publishing)

**Cost: Free.** 10,000 quota units/day. Each upload ~1,600 units.

1. Go to https://console.cloud.google.com/
2. Create a project → Enable **YouTube Data API v3**
3. Create OAuth 2.0 credentials (Desktop app type)
4. Set up OAuth consent screen (add `youtube.upload` scope)
5. Run the following Python script to get a refresh token:

```python
from google_auth_oauthlib.flow import InstalledAppFlow

flow = InstalledAppFlow.from_client_secrets_file(
    'client_secret.json',
    scopes=['https://www.googleapis.com/auth/youtube.upload']
)
creds = flow.run_local_server(port=0)
print(f"Refresh token: {creds.refresh_token}")
```

6. Set in `.env`:
```
YOUTUBE_CLIENT_ID=your_client_id
YOUTUBE_CLIENT_SECRET=your_client_secret
YOUTUBE_REFRESH_TOKEN=your_refresh_token
```

### 5. Upload-Post.com (TikTok + multi-platform publishing)

**Cost: Free tier available (no credit card).**

1. Go to https://www.upload-post.com/ → Sign up
2. Go to API Keys section → Generate a key
3. Set `UPLOAD_POST_API_KEY=your_key` in `.env`

Covers: TikTok, Instagram, YouTube, Facebook with a single API call.

## Usage

### 1. Scraping

- The scheduler runs automatically at your configured interval (default: 24h)
- Click **"Scrape Now"** on the Dashboard to trigger immediately
- Or `curl -X POST http://localhost:8000/api/scrape/trigger`

### 2. Scoring

Every scraped video gets scored 0-100 using:
- Engagement rate (25%)
- Growth velocity (20%)
- Sound trend (15%)
- Hashtag trend (10%)
- Retention estimate (10%)
- Author authority (10%)
- Visual quality (10%)

### 3. Generation

1. Go to the **Generate** tab
2. Click **"Generate New Video"**
3. Wait for processing (30-120s) — the system:
   - Analyzes top 10 scored videos for "winning patterns"
   - Downloads a stock clip from Pexels
   - Transcribes the trending audio with Whisper
   - Burns captions + hook text onto the video
   - Overlays the trending music
4. Preview the video, then click **"Upload Now"**

### 4. Publishing

Select platforms (checkboxes) and:
- Click **"Upload Now"** for immediate publish
- Toggle **"Auto-upload"** to publish immediately after generation

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Health check |
| GET | `/api/stats` | Aggregate statistics |
| GET | `/api/videos/scored` | List scored videos (filterable) |
| GET | `/api/videos/top` | Top 10 scored videos |
| POST | `/api/scrape/trigger` | Trigger immediate scrape |
| POST | `/api/generate` | Trigger video generation |
| GET | `/api/generate/{task_id}/status` | Poll generation status |
| GET | `/api/generate/{task_id}/result` | Get generation result |
| GET | `/api/generated` | List all generated videos |
| GET | `/api/generated/{id}/download` | Download video file |
| GET | `/api/generated/{id}/thumbnail` | Get video thumbnail |
| POST | `/api/upload` | Upload to selected platforms |
| GET | `/api/upload/log` | Upload history |
| GET | `/api/schedule` | Get current schedule |
| PUT | `/api/schedule` | Update scan interval |

## Project Structure

```
createai/
├── .env.example              # Template for environment variables
├── docker-compose.yml        # Full stack orchestration
├── Dockerfile                # All-in-one build (optional)
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
│       ├── main.py           # FastAPI app + routes
│       ├── config.py         # Pydantic settings
│       ├── database.py       # SQLAlchemy async engine
│       ├── models.py         # ORM models
│       ├── scrapers/
│       │   ├── base.py       # Abstract scraper
│       │   ├── instagram.py  # Apify Instagram scraper
│       │   ├── tiktok.py     # TikTokApi scraper (free)
│       │   ├── youtube.py    # yt-dlp scraper (free)
│       │   └── facebook.py   # Apify Facebook scraper
│       ├── scoring/
│       │   └── engine.py     # Virality scoring formula
│       ├── generation/
│       │   ├── pattern.py    # Pattern extraction from top videos
│       │   └── pipeline.py   # Video generation (MoviePy + FFmpeg + Whisper)
│       ├── upload/
│       │   ├── manager.py    # Unified upload orchestrator
│       │   ├── meta.py       # Meta Graph API uploader
│       │   ├── youtube.py    # YouTube Data API uploader
│       │   └── upload_post.py# Upload-Post.com integration
│       └── scheduler/
│           ├── tasks.py      # Celery tasks
│           └── beat.py       # Celery Beat schedule
└── frontend/
    ├── Dockerfile
    ├── package.json
    └── src/
        ├── App.jsx           # Router + layout
        ├── api.js            # Axios API client
        ├── components/
        │   ├── Dashboard.jsx      # Scored videos table + stats
        │   ├── Generator.jsx      # Video generation + preview + upload
        │   ├── ScheduleSettings.jsx # Scan interval config
        │   └── UploadLog.jsx      # Upload history table
        └── index.css         # Tailwind + custom styles
```

## Cost Breakdown

| Component | Cost | Notes |
|-----------|------|-------|
| Apify (Instagram + Facebook) | ~$0.004/video | $5 free credit included |
| Pexels (stock clips) | Free | 200 req/hr limit |
| YouTube scraper (yt-dlp) | Free | No API key needed |
| TikTok scraper (TikTokApi) | Free | Playwright-based |
| Upload-Post.com | Free tier | No credit card |
| YouTube upload | Free | 10K quota/day |
| Meta upload | Free | Page token never expires |
| **Total per 100 videos** | **<$0.01** | Within your budget |

## Tech Stack & Rationale

| Library | Purpose | Why |
|---------|---------|-----|
| **FastAPI** | API framework | Async, auto OpenAPI docs, fast |
| **SQLAlchemy 2.0** | ORM | Mature, async support, Alembic migrations |
| **Celery + Redis** | Task queue | Reliable async task processing |
| **MoviePy 2.x** | Video compositing | Python-native text overlays, audio mixing |
| **FFmpeg** | Video encoding | Industry standard, fastest encoding |
| **Whisper** | Speech-to-text | Free, open-source, accurate |
| **yt-dlp** | YouTube metadata | No API key, full metadata extraction |
| **TikTokApi** | TikTok scraper | Free, trending feed access |
| **Apify Client** | Instagram/Facebook | Cheap, reliable, manageable |
| **Upload-Post SDK** | Publishing | Single API for all platforms, free tier |
| **React + Tailwind** | Frontend | Fast development, clean UI |
| **Vite** | Build tool | Fast HMR, optimized builds |

## Assumptions

1. **Scraping availability**: Open-source scrapers (yt-dlp, TikTokApi) depend on undocumented APIs that may break. Apify is the paid fallback.
2. **Video hosting**: Meta Graph API requires a publicly accessible video URL. The MVP uses file.io or a simple HTTP server as temporary hosting. For production, use S3/GCS.
3. **Audio for generation**: If the scraped video's download URL has expired (common after a few hours), the pipeline falls back to using the hook text as the caption — no music overlay.
4. **Whisper model**: The "base" model (~150MB) runs on CPU in ~1-2x real-time. For faster transcription, switch to "tiny" in `.env`: `WHISPER_MODEL=tiny`.
5. **Resolution estimation**: Resolution is estimated from metadata only. If unavailable, defaults to 720p (score = 0.5).
6. **Docker memory**: Video generation uses FFmpeg + MoviePy, which can be memory-intensive for long clips. The 15-45 second range keeps it manageable.

## Production Considerations

1. **Replace temporary hosting** with S3/GCS for Meta Graph API uploads
2. **Add Celery Flower** for task monitoring
3. **Set up Alembic** for database migrations
4. **Add authentication** (JWT + OAuth)
5. **Use a proper proxy rotation** for scraping at scale
6. **Implement rate limiting** for API endpoints
7. **Add monitoring** (Prometheus + Grafana or Sentry)
