import logging
import statistics
from typing import Any

from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ScoredVideo, ScrapedVideo, AppConfig
from app.database import async_session_factory

logger = logging.getLogger(__name__)

HOOK_STYLES = {
    "question": {"keywords": ["?", "what", "why", "how", "do you", "are you", "have you", "did you", "will you", "can you", "is it", "who"]},
    "statistic": {"keywords": ["%", "percent", "times", "million", "billion", "thousand", "ratio", "numbers", "stat"]},
    "cliffhanger": {"keywords": ["...", "wait till", "you won't believe", "watch until", "but then", "until the end", "what happens next"]},
    "curiosity_gap": {"keywords": ["the reason", "this is why", "here's why", "what happens when", "the truth about", "nobody tells you", "secret"]},
    "story_hook": {"keywords": ["so i", "i was", "my friend", "one day", "when i", "this one", "a guy", "this girl", "we were", "i tried"]},
    "statement": {"keywords": ["this is", "the best", "the worst", "never", "always", "everyone", "nobody", "stop", "you need", "this will"]},
}

CAPTION_STYLES = {
    "storytelling": {"keywords": ["i", "me", "my", "we", "us", "our", "felt", "thought", "realized", "experience", "happened"]},
    "educational": {"keywords": ["how to", "tutorial", "tips", "trick", "learn", "guide", "steps", "beginner", "easy way", "simple"]},
    "call_to_action": {"keywords": ["follow", "like", "share", "comment", "save", "tag", "subscribe", "turn on", "check out", "link in"]},
    "controversial": {"keywords": ["hot take", "unpopular opinion", "change my mind", "debate", "truth", "actually", "wrong", "right?", "prove me"]},
    "humorous": {"keywords": ["lol", "funny", "hilarious", "joke", "memes", "pov", "be like", "relatable", "cursed", "based"]},
    "standard": {"keywords": []},
}


def _classify_hook_style(caption: str) -> tuple[str, float]:
    lower = caption.lower()[:200]
    best_style = "statement"
    best_score = 0.0
    for style, info in HOOK_STYLES.items():
        score = 0.0
        for kw in info["keywords"]:
            if kw in lower:
                score += 1.0
        if lower.endswith("?") and style == "question":
            score += 2.0
        if score > best_score:
            best_score = score
            best_style = style
    return best_style, best_score


def _classify_caption_style(caption: str) -> tuple[str, float]:
    lower = caption.lower()
    best_style = "standard"
    best_score = 0.0
    for style, info in CAPTION_STYLES.items():
        if style == "standard":
            continue
        score = 0.0
        for kw in info["keywords"]:
            count = lower.count(kw)
            if count > 0:
                score += count * 2.0 if len(kw.split()) > 1 else count
        if score > best_score:
            best_score = score
            best_style = style
    return best_style, best_score


async def analyze_strategy(session: AsyncSession | None = None) -> dict[str, Any]:
    if session is None:
        async with async_session_factory() as s:
            return await _analyze(s)
    return await _analyze(session)


async def _analyze(session: AsyncSession) -> dict[str, Any]:
    result = await session.execute(
        select(ScoredVideo)
        .order_by(ScoredVideo.virality_score.desc())
        .limit(50)
    )
    scored_videos = result.scalars().all()
    if not scored_videos:
        return _default_strategy()

    top_videos = []
    for sv in scored_videos:
        scraped = await session.get(ScrapedVideo, sv.scraped_video_id)
        if scraped:
            top_videos.append({"scored": sv, "scraped": scraped})

    hook_classifications = {}
    caption_classifications = {}
    durations = []
    hashtag_freq = {}
    music_usage = 0
    resolution_heights = []
    virality_scores_per_hook = {}
    virality_scores_per_caption = {}

    for item in top_videos:
        sv = item["scored"]
        scraped = item["scraped"]
        caption = scraped.caption or ""
        score = sv.virality_score

        hook_style, hook_conf = _classify_hook_style(caption)
        hook_classifications[hook_style] = hook_classifications.get(hook_style, 0) + 1
        if hook_style not in virality_scores_per_hook:
            virality_scores_per_hook[hook_style] = []
        virality_scores_per_hook[hook_style].append(score)

        caption_style, cap_conf = _classify_caption_style(caption)
        caption_classifications[caption_style] = caption_classifications.get(caption_style, 0) + 1
        if caption_style not in virality_scores_per_caption:
            virality_scores_per_caption[caption_style] = []
        virality_scores_per_caption[caption_style].append(score)

        if scraped.duration:
            durations.append(scraped.duration)
        for h in (scraped.hashtags or []):
            h_lower = h.lower().strip("#")
            if h_lower:
                hashtag_freq[h_lower] = hashtag_freq.get(h_lower, 0) + 1
        if scraped.music:
            music_usage += 1
        if scraped.resolution_height:
            resolution_heights.append(scraped.resolution_height)

    def best_by_frequency(classifications: dict) -> str:
        if not classifications:
            return "standard"
        return max(classifications, key=classifications.get)

    def best_by_avg_score(score_map: dict) -> str:
        valid = {k: statistics.mean(v) for k, v in score_map.items() if len(v) >= 2}
        if not valid:
            return best_by_frequency(
                {k: len(v) for k, v in score_map.items()}
            )
        return max(valid, key=valid.get)

    recommended_hook = best_by_avg_score(virality_scores_per_hook)
    recommended_caption = best_by_avg_score(virality_scores_per_caption)

    avg_duration = statistics.mean(durations) if durations else 30
    target_duration = max(15, min(45, int(avg_duration)))

    sorted_hashtags = sorted(hashtag_freq.items(), key=lambda x: -x[1])[:10]
    top_hashtags = [t for t, _ in sorted_hashtags]

    music_ratio = round(music_usage / len(top_videos), 2)
    use_music = music_ratio > 0.3

    avg_resolution = statistics.mode(resolution_heights) if resolution_heights else 1920
    if avg_resolution >= 1920:
        recommended_resolution = "1080x1920"
    elif avg_resolution >= 1080:
        recommended_resolution = "720x1280"
    else:
        recommended_resolution = "480x854"

    strategy = {
        "recommended_hook_style": recommended_hook,
        "recommended_caption_style": recommended_caption,
        "recommended_duration": target_duration,
        "recommended_resolution": recommended_resolution,
        "recommended_hashtags": top_hashtags[:5],
        "recommend_music": use_music,
        "hook_distribution": hook_classifications,
        "caption_distribution": caption_classifications,
        "hook_performance": {k: round(statistics.mean(v), 2) for k, v in virality_scores_per_hook.items() if v},
        "caption_performance": {k: round(statistics.mean(v), 2) for k, v in virality_scores_per_caption.items() if v},
        "top_hashtags_frequency": top_hashtags,
        "avg_duration": round(avg_duration, 1),
        "music_ratio": music_ratio,
        "avg_virality_score": round(statistics.mean([v for v, _ in [(sv.virality_score, None) for sv in scored_videos]]), 2),
        "videos_analyzed": len(top_videos),
    }

    await _save_strategy(session, strategy)
    return strategy


async def _save_strategy(session: AsyncSession, strategy: dict):
    result = await session.execute(
        select(AppConfig).where(AppConfig.key == "strategy")
    )
    config = result.scalar_one_or_none()
    if config:
        config.value = strategy
    else:
        config = AppConfig(key="strategy", value=strategy)
        session.add(config)
    await session.commit()


async def load_strategy(session: AsyncSession | None = None) -> dict[str, Any]:
    if session is None:
        async with async_session_factory() as s:
            return await _load_strategy(s)
    return await _load_strategy(session)


async def _load_strategy(session: AsyncSession) -> dict[str, Any]:
    result = await session.execute(
        select(AppConfig).where(AppConfig.key == "strategy")
    )
    config = result.scalar_one_or_none()
    if config and config.value:
        return config.value
    return _default_strategy()


def _default_strategy() -> dict[str, Any]:
    return {
        "recommended_hook_style": "question",
        "recommended_caption_style": "standard",
        "recommended_duration": 30,
        "recommended_resolution": "1080x1920",
        "recommended_hashtags": ["viral", "fyp", "trending", "reels", "shorts"],
        "recommend_music": True,
        "hook_distribution": {},
        "caption_distribution": {},
        "hook_performance": {},
        "caption_performance": {},
        "top_hashtags_frequency": [],
        "avg_duration": 30.0,
        "music_ratio": 0.0,
        "avg_virality_score": 0.0,
        "videos_analyzed": 0,
    }
