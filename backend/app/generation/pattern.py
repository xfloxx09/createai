from typing import Any
import statistics
import random


def extract_patterns(top_videos: list[dict], strategy: dict | None = None) -> dict[str, Any]:
    if not top_videos:
        return _default_patterns(strategy)

    captions = [v.get("caption", "") or "" for v in top_videos]
    durations = [v.get("duration", 0) or 0 for v in top_videos]
    hashtag_lists = [v.get("hashtags", []) or [] for v in top_videos]
    music_list = [v.get("music") for v in top_videos if v.get("music")]
    scores = [v.get("virality_score", 0) for v in top_videos]

    best = top_videos[0]
    best_caption = best.get("caption", "") or ""

    hook_style = (strategy or {}).get("recommended_hook_style", "question")
    caption_style = (strategy or {}).get("recommended_caption_style", "standard")
    strategy_hashtags = (strategy or {}).get("recommended_hashtags", [])

    hook_text = _build_hook(best_caption, hook_style)

    all_hashtags = []
    for hl in hashtag_lists:
        all_hashtags.extend(hl)

    strategy_tags = [h for h in strategy_hashtags if any(h.lower() in (t.lower() for t in all_hashtags))]
    frequent_tags = [h for h in all_hashtags if all_hashtags.count(h) > 1]
    seen = set()
    merged_tags = []
    for tag in strategy_tags + frequent_tags:
        if tag.lower() not in seen:
            merged_tags.append(tag)
            seen.add(tag.lower())
    top_hashtags = merged_tags[:5] or all_hashtags[:5]

    avg_duration = statistics.mean(durations) if durations else 30
    strategy_duration = (strategy or {}).get("recommended_duration")
    target_duration = strategy_duration if strategy_duration else max(15, min(45, int(avg_duration)))

    avg_score = statistics.mean(scores) if scores else 50

    recommend_music = (strategy or {}).get("recommend_music", True)
    music_genre = _detect_music_genre(music_list) if music_list else "trending_pop"

    return {
        "hook_text": hook_text,
        "hook_style": hook_style,
        "caption_style": caption_style,
        "target_duration": target_duration,
        "top_hashtags": top_hashtags,
        "caption_structure": "question_hook" if hook_text.endswith("?") else "statement_hook",
        "music_genre": music_genre,
        "use_music": recommend_music and bool(music_list),
        "avg_virality_score": round(avg_score, 1),
        "source_count": len(top_videos),
        "text_overlay_position": "bottom_third",
    }


def _build_hook(caption: str, hook_style: str) -> str:
    lines = [l.strip() for l in caption.split("\n") if l.strip()]
    first_line = ""
    for line in lines:
        clean = line.split("#")[0].strip()
        if clean and len(clean) > 5:
            first_line = clean[:120]
            break
    if not first_line:
        first_line = "Did you know this?"

    if hook_style == "question":
        if not first_line.endswith("?"):
            templates = [
                f"Did you know {first_line.lower()}?",
                f"Have you seen {first_line.lower()}?",
                f"Can you believe {first_line.lower()}?",
                f"What if {first_line.lower()}?",
            ]
            return random.choice(templates)
        return first_line
    elif hook_style == "statistic":
        return f"{first_line.split('.')[0]} - here's why it matters."
    elif hook_style == "cliffhanger":
        if not first_line.endswith("..."):
            return f"{first_line.rsplit('.', 1)[0]}... wait till you see this."
        return first_line
    elif hook_style == "curiosity_gap":
        return f"The truth about {first_line.split()[0] if first_line.split() else 'this'} will surprise you."
    elif hook_style == "story_hook":
        return f"So I found something incredible: {first_line.lower()}"
    else:
        return first_line


def _detect_music_genre(music_list: list) -> str:
    if not music_list:
        return "trending_pop"
    return "trending_pop"


def _default_patterns(strategy: dict | None = None) -> dict[str, Any]:
    s = strategy or {}
    return {
        "hook_text": "Did you know this?",
        "hook_style": s.get("recommended_hook_style", "question"),
        "caption_style": s.get("recommended_caption_style", "standard"),
        "target_duration": s.get("recommended_duration", 30),
        "top_hashtags": s.get("recommended_hashtags", ["viral", "fyp", "trending"]),
        "caption_structure": "question_hook",
        "music_genre": "trending_pop",
        "use_music": s.get("recommend_music", True),
        "avg_virality_score": 0.0,
        "source_count": 0,
        "text_overlay_position": "bottom_third",
    }
