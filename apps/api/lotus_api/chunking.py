from dataclasses import dataclass

from .models import TranscriptSegment


@dataclass(frozen=True)
class TranscriptChunk:
    index: int
    start_ms: int
    end_ms: int
    speakers: tuple[str, ...]
    segment_ids: tuple[str, ...]
    text: str


def chunk_transcript(
    segments: list[TranscriptSegment],
    target_words: int = 120,
    overlap_segments: int = 1,
) -> list[TranscriptChunk]:
    ordered = sorted(segments, key=lambda item: (item.start_ms, item.end_ms))
    chunks: list[TranscriptChunk] = []
    cursor = 0
    while cursor < len(ordered):
        selected: list[TranscriptSegment] = []
        words = 0
        for segment in ordered[cursor:]:
            selected.append(segment)
            words += len(segment.text.split())
            if words >= target_words:
                break
        if not selected:
            break
        chunks.append(
            TranscriptChunk(
                index=len(chunks),
                start_ms=selected[0].start_ms,
                end_ms=selected[-1].end_ms,
                speakers=tuple(dict.fromkeys(item.speaker for item in selected)),
                segment_ids=tuple(item.segment_id for item in selected),
                text="\n".join(f"{item.speaker}: {item.text}" for item in selected),
            )
        )
        if selected[-1] is ordered[-1]:
            break
        cursor += max(1, len(selected) - overlap_segments)
    return chunks
