import asyncio
import json
import os
import random
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Optional

import requests
from moviepy import (
    VideoFileClip,
    AudioFileClip,
    TextClip,
    CompositeVideoClip,
    concatenate_videoclips,
)

from app.config import settings
from app.generation.pattern import extract_patterns
from app.costs import COST_PER_SCRAPE, COST_PER_GENERATE, COST_PER_UPLOAD


class VideoGenerationPipeline:
    def __init__(self):
        self.temp_dir = Path(settings.temp_dir) / "generation"
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    async def generate(self, top_videos: list[dict]) -> dict:
        patterns = extract_patterns(top_videos)
        task_id = str(uuid.uuid4())[:8]
        work_dir = self.temp_dir / task_id
        work_dir.mkdir(parents=True, exist_ok=True)

        stock_video_path = await asyncio.to_thread(
            self._download_stock_clip, work_dir
        )

        music_path = None
        audio_path = None
        if top_videos and top_videos[0].get("download_url"):
            music_path, audio_path = await asyncio.to_thread(
                self._download_music, top_videos[0], work_dir
            )

        caption_text = patterns["hook_text"]
        if audio_path:
            transcription = await asyncio.to_thread(
                self._transcribe_audio, audio_path
            )
            if transcription and len(transcription) > 5:
                caption_text = transcription

        output_path = work_dir / "output.mp4"
        thumbnail_path = work_dir / "thumbnail.jpg"

        await asyncio.to_thread(
            self._render_video,
            stock_video_path=stock_video_path,
            music_path=music_path,
            caption_text=caption_text,
            output_path=output_path,
            thumbnail_path=thumbnail_path,
            target_duration=patterns["target_duration"],
        )

        generated_caption = self._build_caption(caption_text, patterns["top_hashtags"])

        scrape_costs = {}
        for v in top_videos:
            p = v.get("platform", "")
            scrape_costs[p] = COST_PER_SCRAPE.get(p, 0)
        total_scrape_cost = sum(scrape_costs.values())
        total_gen_cost = sum(COST_PER_GENERATE.values())
        total_cost = round(total_scrape_cost + total_gen_cost, 6)
        cost_breakdown = {
            "scrape": {"per_video": scrape_costs, "total": round(total_scrape_cost, 6)},
            "generate": {k: v for k, v in COST_PER_GENERATE.items()},
            "total": total_cost,
        }

        return {
            "task_id": task_id,
            "output_path": str(output_path),
            "thumbnail_path": str(thumbnail_path) if thumbnail_path.exists() else None,
            "caption": generated_caption,
            "hook_text": caption_text,
            "duration": patterns["target_duration"],
            "pattern_breakdown": patterns,
            "total_cost": total_cost,
            "cost_breakdown": cost_breakdown,
        }

    def _download_stock_clip(self, work_dir: Path) -> str:
        if settings.pexels_api_key:
            try:
                return self._download_from_pexels(work_dir)
            except Exception:
                pass
        return self._generate_fallback_clip(work_dir)

    def _download_from_pexels(self, work_dir: Path) -> str:
        headers = {"Authorization": settings.pexels_api_key}
        queries = ["trending", "viral", "lifestyle", "nature", "city", "technology"]
        query = random.choice(queries)
        resp = requests.get(
            f"https://api.pexels.com/videos/search?query={query}&per_page=10&orientation=portrait&size=medium",
            headers=headers,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        videos = data.get("videos", [])
        if not videos:
            raise RuntimeError("No videos from Pexels")

        video = random.choice(videos)
        video_files = video.get("video_files", [])
        mp4_files = [f for f in video_files if f.get("file_type") == "video/mp4" and f.get("height", 0) >= 720]
        if not mp4_files:
            mp4_files = video_files
        chosen = mp4_files[0]
        file_url = chosen.get("link")
        if not file_url:
            raise RuntimeError("No download link in Pexels response")

        out_path = work_dir / "stock.mp4"
        r = requests.get(file_url, timeout=120)
        r.raise_for_status()
        out_path.write_bytes(r.content)
        return str(out_path)

    def _generate_fallback_clip(self, work_dir: Path) -> str:
        out_path = work_dir / "fallback.mp4"
        width, height = 540, 960
        duration = 30
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", f"color=c=#1a1a2e:s={width}x{height}:d={duration}:r=30",
            "-vf", "drawtext=text='':fontsize=1",
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-pix_fmt", "yuv420p",
            str(out_path),
        ]
        subprocess.run(cmd, check=True, capture_output=True, timeout=120)
        return str(out_path)

    def _download_music(self, top_video: dict, work_dir: Path):
        download_url = top_video.get("download_url")
        if not download_url:
            return None, None

        music_path = work_dir / "music.mp3"
        try:
            r = requests.get(download_url, timeout=120, stream=True)
            if r.status_code != 200:
                return None, None
            with open(music_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)

            audio_path = work_dir / "audio.mp3"
            subprocess.run(
                ["ffmpeg", "-y", "-i", str(music_path), "-vn", "-acodec", "mp3", str(audio_path)],
                check=True, capture_output=True, timeout=60,
            )
            return str(music_path), str(audio_path)
        except Exception:
            return None, None

    def _transcribe_audio(self, audio_path: str) -> Optional[str]:
        try:
            import whisper
            model = whisper.load_model(settings.whisper_model)
            result = model.transcribe(audio_path, language="en")
            return result.get("text", "").strip()
        except Exception:
            return None

    def _render_video(
        self,
        stock_video_path: str,
        music_path: Optional[str],
        caption_text: str,
        output_path: Path,
        thumbnail_path: Path,
        target_duration: int,
    ):
        clip = VideoFileClip(stock_video_path)
        clip = clip.resize(height=960)
        clip = clip.crop(x_center=clip.w / 2, y_center=clip.h / 2, width=540, height=960)

        if clip.duration < 1:
            clip = clip.loop(duration=target_duration)
        elif clip.duration > target_duration:
            clip = clip.subclip(0, target_duration)
        elif clip.duration < target_duration:
            clip = clip.loop(duration=target_duration)

        words = caption_text.split()
        chunks = []
        current = ""
        for w in words:
            test = f"{current} {w}".strip()
            if len(test) <= 45:
                current = test
            else:
                chunks.append(current)
                current = w
        if current:
            chunks.append(current)
        display_text = "\n".join(chunks[:6])

        txt_clip = TextClip(
            text=display_text,
            font="Arial",
            font_size=42,
            color="white",
            stroke_color="black",
            stroke_width=2,
            method="caption",
            size=(500, None),
        )
        txt_clip = txt_clip.with_position(("center", "bottom")).with_duration(clip.duration).with_start(1)

        txt_bg = TextClip(
            text="",
            font="Arial",
            font_size=42,
            color="black",
            size=(540, 180),
        )
        txt_bg = txt_bg.with_position(("center", "bottom")).with_duration(clip.duration).with_start(1).with_opacity(0)

        final = CompositeVideoClip([clip, txt_clip], size=(540, 960))

        if music_path:
            try:
                audio = AudioFileClip(music_path)
                if audio.duration > final.duration:
                    audio = audio.subclip(0, final.duration)
                elif audio.duration > 0:
                    audio = audio.loop(duration=final.duration) if audio.duration < final.duration else audio
                final = final.with_audio(audio)
            except Exception:
                pass

        final.write_videofile(
            str(output_path),
            codec="libx264",
            audio_codec="aac",
            fps=30,
            preset="medium",
            bitrate="2000k",
            threads=2,
            logger=None,
        )

        try:
            subprocess.run(
                ["ffmpeg", "-y", "-i", str(output_path), "-ss", "00:00:01", "-vframes", "1", str(thumbnail_path)],
                check=True, capture_output=True, timeout=30,
            )
        except Exception:
            pass

        clip.close()
        if music_path:
            try:
                audio.close()
            except Exception:
                pass

    def _build_caption(self, hook: str, hashtags: list) -> str:
        selected = hashtags[:5] if hashtags else ["viral", "fyp", "trending", "reels", "shorts"]
        tag_str = " ".join(f"#{t}" if not t.startswith("#") else t for t in selected)
        return f"{hook}\n\n{tag_str}".strip()

    def cleanup(self, task_id: str):
        work_dir = self.temp_dir / task_id
        if work_dir.exists():
            import shutil
            shutil.rmtree(work_dir)
