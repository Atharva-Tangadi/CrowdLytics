import React, { useRef, useEffect, useState, useMemo, useCallback } from 'react';
import { AnalysisResult, AnalysisChunk, FrameAnnotation, FrameGroupAnnotation } from '../../types/api';
import { Eye, EyeOff, Sliders, Compass, Loader2 } from 'lucide-react';

interface ResultCanvasProps {
  mediaUrl: string;
  result?: AnalysisResult | null;
  chunks?: AnalysisChunk[];
  mediaType: 'IMAGE' | 'VIDEO';
  isAnalyzing?: boolean;
  showHulls?: boolean;
  showCentroids?: boolean;
  showBoxes?: boolean;
}

const CLUSTER_HEX = [
  '#ef4444', // Red
  '#3b82f6', // Blue
  '#10b981', // Emerald
  '#f59e0b', // Amber
  '#a855f7', // Purple
  '#ec4899', // Pink
  '#06b6d4', // Cyan
  '#eab308', // Yellow
];

export const ResultCanvas: React.FC<ResultCanvasProps> = ({
  mediaUrl,
  result,
  chunks = [],
  mediaType,
  isAnalyzing = false,
  showHulls = true,
  showCentroids = true,
  showBoxes = true,
}) => {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const videoRef = useRef<HTMLVideoElement | null>(null);

  // Playback & Overlay states
  const [showOverlays, setShowOverlays] = useState<boolean>(true);
  const [detailedMode, setDetailedMode] = useState<boolean>(false);
  const [currentTime, setCurrentTime] = useState<number>(0);
  const [duration, setDuration] = useState<number>(0);
  const [currentFrameData, setCurrentFrameData] = useState<FrameAnnotation | null>(null);

  // Parse all frame annotations from completed chunks sorted by timestamp
  const allFrames: FrameAnnotation[] = useMemo(() => {
    if (!chunks || chunks.length === 0) return [];
    const frames: FrameAnnotation[] = [];
    for (const chunk of chunks) {
      try {
        const parsed: FrameAnnotation[] = JSON.parse(chunk.frame_data_json);
        frames.push(...parsed);
      } catch {
        // Skip malformed chunk json
      }
    }
    return frames.sort((a, b) => a.timestamp - b.timestamp);
  }, [chunks]);

  const latestAnalyzedTimestamp = useMemo(() => {
    if (allFrames.length === 0) return 0;
    return allFrames[allFrames.length - 1].timestamp;
  }, [allFrames]);

  // Find frame closest to target timestamp within tolerance (0.45s)
  const findMatchingFrame = useCallback(
    (time: number): FrameAnnotation | null => {
      if (allFrames.length === 0) return null;
      let closest: FrameAnnotation | null = null;
      let minDiff = 0.45;

      for (const f of allFrames) {
        const diff = Math.abs(f.timestamp - time);
        if (diff < minDiff) {
          minDiff = diff;
          closest = f;
        }
      }
      return closest;
    },
    [allFrames]
  );

  // --- Draw Image Analysis Overlays ---
  const renderImageOverlay = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas || !result) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const img = new Image();
    img.crossOrigin = 'anonymous';
    img.src = mediaUrl;
    img.onload = () => {
      canvas.width = img.width;
      canvas.height = img.height;
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.drawImage(img, 0, 0);

      if (!showOverlays) return;

      result.groups.forEach((group, idx) => {
        const color = CLUSTER_HEX[idx % CLUSTER_HEX.length];

        // 1. Bounding Box
        if (showBoxes && group.bounding_box_json) {
          try {
            const bbox = JSON.parse(group.bounding_box_json);
            const [minX, minY, maxX, maxY] = bbox;
            ctx.strokeStyle = color;
            ctx.lineWidth = 2;
            ctx.strokeRect(minX, minY, maxX - minX, maxY - minY);

            ctx.fillStyle = color;
            ctx.font = 'bold 12px Inter, sans-serif';
            ctx.fillText(
              `Group ${group.cluster_id} (n=${group.member_count})`,
              minX,
              Math.max(minY - 6, 14)
            );
          } catch {}
        }

        // 2. Centroid
        if (showCentroids) {
          ctx.fillStyle = color;
          ctx.beginPath();
          ctx.arc(group.centroid_x, group.centroid_y, 5, 0, Math.PI * 2);
          ctx.fill();
          ctx.strokeStyle = '#ffffff';
          ctx.lineWidth = 1.5;
          ctx.stroke();
        }
      });
    };
  }, [mediaUrl, result, showOverlays, showBoxes, showCentroids]);

  // --- Draw Video Analysis Overlays ---
  const renderVideoOverlay = useCallback(() => {
    const canvas = canvasRef.current;
    const video = videoRef.current;
    if (!canvas || !video) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Synchronize canvas resolution with video intrinsic dimensions
    const vw = video.videoWidth || 640;
    const vh = video.videoHeight || 360;
    if (canvas.width !== vw || canvas.height !== vh) {
      canvas.width = vw;
      canvas.height = vh;
    }

    ctx.clearRect(0, 0, canvas.width, canvas.height);

    if (!showOverlays) {
      setCurrentFrameData(null);
      return;
    }

    const t = video.currentTime;
    const frame = findMatchingFrame(t);
    setCurrentFrameData(frame);

    if (!frame || !frame.groups || frame.groups.length === 0) {
      return;
    }

    // Draw each group in the active frame
    frame.groups.forEach((group: FrameGroupAnnotation) => {
      const color = CLUSTER_HEX[(group.group_id - 1) % CLUSTER_HEX.length];

      // 1. Convex Hull Polygon Boundary
      if (showHulls && group.convex_hull && group.convex_hull.length >= 3) {
        ctx.beginPath();
        const [firstX, firstY] = group.convex_hull[0];
        ctx.moveTo(firstX, firstY);
        for (let i = 1; i < group.convex_hull.length; i++) {
          ctx.lineTo(group.convex_hull[i][0], group.convex_hull[i][1]);
        }
        ctx.closePath();

        // Semi-transparent polygon fill
        ctx.fillStyle = `${color}33`; // 20% alpha
        ctx.fill();
        ctx.strokeStyle = color;
        ctx.lineWidth = 2.5;
        ctx.stroke();
      }

      // 2. Centroid Marker
      if (showCentroids) {
        const [cx, cy] = group.centroid;
        ctx.beginPath();
        ctx.arc(cx, cy, 5, 0, Math.PI * 2);
        ctx.fillStyle = color;
        ctx.fill();
        ctx.strokeStyle = '#ffffff';
        ctx.lineWidth = 2;
        ctx.stroke();
      }

      // 3. Collective Movement Direction Arrow
      if (
        group.motion_angle_deg !== null &&
        group.direction_label !== 'STATIONARY' &&
        group.motion_speed >= 0.5
      ) {
        const [cx, cy] = group.centroid;
        const rad = (group.motion_angle_deg * Math.PI) / 180.0;
        const arrowLen = Math.min(Math.max(group.motion_speed * 8.0, 24), 60);
        const endX = cx + Math.cos(rad) * arrowLen;
        const endY = cy + Math.sin(rad) * arrowLen;

        // Shaft
        ctx.beginPath();
        ctx.moveTo(cx, cy);
        ctx.lineTo(endX, endY);
        ctx.strokeStyle = '#facc15'; // Bright yellow arrow
        ctx.lineWidth = 3;
        ctx.stroke();

        // Arrowhead
        const headLen = 9;
        const angle1 = rad - Math.PI / 6;
        const angle2 = rad + Math.PI / 6;
        ctx.beginPath();
        ctx.moveTo(endX, endY);
        ctx.lineTo(endX - headLen * Math.cos(angle1), endY - headLen * Math.sin(angle1));
        ctx.lineTo(endX - headLen * Math.cos(angle2), endY - headLen * Math.sin(angle2));
        ctx.closePath();
        ctx.fillStyle = '#facc15';
        ctx.fill();
      }

      // 4. Stable Group Badge & Direction Label
      const [minX, minY] = group.bounding_box;
      const labelX = Math.max(minX, 10);
      const labelY = Math.max(minY - 10, 16);

      // Badge background pill
      const dirText =
        group.direction_label !== 'STATIONARY'
          ? ` ${group.direction_label}`
          : '';
      const mainLabel = `G${group.group_id} (n=${group.member_count})${dirText}`;

      ctx.font = 'bold 12px Inter, sans-serif';
      const textWidth = ctx.measureText(mainLabel).width;
      ctx.fillStyle = 'rgba(15, 23, 42, 0.85)';
      ctx.fillRect(labelX - 4, labelY - 14, textWidth + 8, 18);

      ctx.fillStyle = color;
      ctx.fillText(mainLabel, labelX, labelY);

      // Detailed Metrics Badge
      if (detailedMode) {
        const detailText = `${group.density_per_kpx} /kpx² | NN:${group.mean_nn_distance}px | ${group.formation_state}`;
        ctx.font = '10px Inter, sans-serif';
        const dWidth = ctx.measureText(detailText).width;
        ctx.fillStyle = 'rgba(15, 23, 42, 0.85)';
        ctx.fillRect(labelX - 4, labelY + 6, dWidth + 8, 15);
        ctx.fillStyle = '#94a3b8';
        ctx.fillText(detailText, labelX, labelY + 18);
      }
    });
  }, [showOverlays, showHulls, showCentroids, detailedMode, findMatchingFrame]);

  // Initial draw / change triggers
  useEffect(() => {
    if (mediaType === 'IMAGE') {
      renderImageOverlay();
    } else {
      renderVideoOverlay();
    }
  }, [mediaType, renderImageOverlay, renderVideoOverlay]);

  // Video event listeners for synchronized playback
  const handleTimeUpdate = () => {
    if (videoRef.current) {
      setCurrentTime(videoRef.current.currentTime);
      renderVideoOverlay();
    }
  };

  const handleLoadedMetadata = () => {
    if (videoRef.current) {
      setDuration(videoRef.current.duration || 0);
      renderVideoOverlay();
    }
  };

  const isBuffering =
    mediaType === 'VIDEO' &&
    currentTime > latestAnalyzedTimestamp + 0.5 &&
    (isAnalyzing || latestAnalyzedTimestamp === 0);

  return (
    <div className="flex flex-col gap-3">
      {/* Visual Composition Container */}
      <div
        ref={containerRef}
        className="relative rounded-2xl overflow-hidden border border-slate-700/80 bg-slate-950 flex items-center justify-center min-h-[360px] shadow-2xl"
      >
        {mediaType === 'IMAGE' ? (
          <canvas ref={canvasRef} className="max-w-full h-auto object-contain" />
        ) : (
          <div className="relative w-full h-full flex items-center justify-center">
            <video
              ref={videoRef}
              src={mediaUrl}
              controls
              playsInline
              onTimeUpdate={handleTimeUpdate}
              onSeeked={handleTimeUpdate}
              onLoadedMetadata={handleLoadedMetadata}
              className="w-full max-h-[600px] object-contain"
            />
            {/* Synchronized Overlay Canvas */}
            <canvas
              ref={canvasRef}
              className="pointer-events-none absolute inset-0 w-full h-full object-contain"
            />

            {/* Buffering / Unanalyzed Fallback Indicator */}
            {isBuffering && (
              <div className="absolute top-4 right-4 px-3 py-1.5 rounded-lg bg-amber-500/20 border border-amber-500/40 backdrop-blur-md text-amber-300 text-xs font-medium flex items-center gap-2 pointer-events-none shadow-lg">
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                <span>Buffering analysis for this segment...</span>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Synchronized Video Controls & Overlay Toggles */}
      <div className="flex flex-wrap items-center justify-between gap-3 p-3 bg-slate-800/80 rounded-xl border border-slate-700/70 text-xs">
        <div className="flex items-center gap-2">
          {/* Overlay Visibility Toggle */}
          <button
            type="button"
            onClick={() => {
              setShowOverlays(!showOverlays);
              if (mediaType === 'VIDEO') renderVideoOverlay();
            }}
            className={`px-3 py-1.5 rounded-lg font-medium flex items-center gap-1.5 transition-colors cursor-pointer ${
              showOverlays
                ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 hover:bg-emerald-500/30'
                : 'bg-slate-700 text-slate-400 hover:bg-slate-600'
            }`}
          >
            {showOverlays ? <Eye className="w-3.5 h-3.5" /> : <EyeOff className="w-3.5 h-3.5" />}
            {showOverlays ? 'Overlays Visible' : 'Original Video (Clean)'}
          </button>

          {/* Detailed vs Clean Toggle */}
          {mediaType === 'VIDEO' && showOverlays && (
            <button
              type="button"
              onClick={() => {
                setDetailedMode(!detailedMode);
                renderVideoOverlay();
              }}
              className={`px-3 py-1.5 rounded-lg font-medium flex items-center gap-1.5 transition-colors cursor-pointer ${
                detailedMode
                  ? 'bg-purple-500/20 text-purple-300 border border-purple-500/40 hover:bg-purple-500/30'
                  : 'bg-slate-700 text-slate-400 hover:bg-slate-600'
              }`}
            >
              <Sliders className="w-3.5 h-3.5" />
              {detailedMode ? 'Detailed Mode' : 'Clean Mode'}
            </button>
          )}
        </div>

        {/* Video Progressive Status Information */}
        {mediaType === 'VIDEO' && (
          <div className="flex items-center gap-4 text-slate-400">
            {currentFrameData && currentFrameData.groups.length > 0 && (
              <div className="flex items-center gap-1.5 text-emerald-400">
                <Compass className="w-3.5 h-3.5" />
                <span>
                  Active Groups: {currentFrameData.groups.length} (n={currentFrameData.crowd_count})
                </span>
              </div>
            )}
            <div className="text-slate-300">
              Time:{' '}
              <span className="font-mono text-white">
                {currentTime.toFixed(1)}s / {duration.toFixed(1)}s
              </span>
            </div>
            {chunks.length > 0 && (
              <div className="text-[11px] px-2 py-0.5 rounded bg-slate-900 border border-slate-700 text-slate-300">
                Chunks Ready: {chunks.length} ({latestAnalyzedTimestamp.toFixed(1)}s analyzed)
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
