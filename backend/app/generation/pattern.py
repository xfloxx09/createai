from typing import Any
import statistics


def extract_patterns(top_videos: list[dict]) -> dict[str, Any]:
    if not top_videos:
        return _default_patterns()

    captions = [v.get("caption", "") or "" for v in top_videos]
    durations = [v.get("duration", 0) or 0 for v in top_videos]
    hashtag_lists = [v.get("hashtags", []) or [] for v in top_videos]
    music_list = [v.get("music") for v in top_videos if v.get("music")]
    scores = [v.get("virality_score", 0) for v in top_videos]

    best = top_videos[0]
    best_caption = best.get("caption", "") or ""
    hook_text = _extract_hook(best_caption)

    all_hashtags = []
    for hl in hashtag_lists:
        all_hashtags.extend(hl)
    top_hashtags = [h for h in all_hashtags if all_hashtags.count(h) > 1]
    top_hashtags = list(dict.fromkeys(top_hashtags))[:5]

    avg_duration = statistics.mean(durations) if durations else 30
    target_duration = max(15, min(45, int(avg_duration)))

    avg_score = statistics.mean(scores) if scores else 50

    return {
        "hook_text": hook_text,
        "target_duration": target_duration,
        "top_hashtags": top_hashtags,
        "caption_structure": "question_hook" if hook_text.endswith("?") else "statement_hook",
        "music_genre": _detect_music_genre(music_list),
        "avg_virality_score": round(avg_score, 1),
        "source_count": len(top_videos),
        "text_overlay_position": "bottom_third",
    }


def _extract_hook(caption: str) -> str:
    lines = [l.strip() for l in caption.split("\n") if l.strip()]
    for line in lines:
        line_clean = line.split("#")[0].strip()
        if line_clean and len(line_clean) > 5:
            return line_clean[:120]
    return "Did you know this?"


def _detect_music_genre(music_list: list) -> str:
    if not music_list:
        return "trending_pop"
    return "trending_pop"


def _default_patterns() -> dict[str, Any]:
    return {
        "hook_text": "Did you know this?",
        "target_duration": 30,
        "top_hashtags": ["viral", "fyp", "trending"],
        "caption_structure": "question_hook",
        "music_genre": "trending_pop",
        "avg_virality_score": 0.0,
        "source_count": 0,
        "text_overlay_position": "bottom_third",
    }
