import { AnalysisResult, FrameAnnotation, FrameGroupAnnotation } from '../../types/api';

export function details(result?: AnalysisResult | null): {
  annotation_version?: number;
  group_annotations?: Partial<FrameGroupAnnotation>[];
  crowd_events?: import('../../types/api').CrowdEvent[];
  media_type?: string;
  detector?: string;
} {
  try { return JSON.parse(result?.summary_data_json || '{}'); } catch { return {}; }
}

// Causal lookup: never show a future annotation, or hold one beyond its coverage.
export function matchingFrame(frames: FrameAnnotation[], time: number): FrameAnnotation | null {
  let low = 0, high = frames.length - 1, found = -1;
  while (low <= high) {
    const mid = (low + high) >> 1;
    if (frames[mid].timestamp <= time) { found = mid; low = mid + 1; }
    else high = mid - 1;
  }
  if (found < 0) return null;
  const frame = frames[found];
  const end = frame.valid_until ?? Math.min(frames[found + 1]?.timestamp ?? Infinity, frame.timestamp + .45);
  return time < Math.min(end, frames[found + 1]?.timestamp ?? Infinity) ? frame : null;
}
