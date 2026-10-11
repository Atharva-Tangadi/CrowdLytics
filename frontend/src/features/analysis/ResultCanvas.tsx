import React, { useRef, useEffect } from 'react';
import { AnalysisResult } from '../../types/api';

interface ResultCanvasProps {
  mediaUrl: string;
  result: AnalysisResult;
  mediaType: 'IMAGE' | 'VIDEO';
  showHulls?: boolean;
  showCentroids?: boolean;
  showBoxes?: boolean;
}

const CLUSTER_HEX = [
  '#ef4444',
  '#3b82f6',
  '#10b981',
  '#f59e0b',
  '#a855f7',
  '#ec4899',
  '#06b6d4',
  '#eab308',
];

export const ResultCanvas: React.FC<ResultCanvasProps> = ({
  mediaUrl,
  result,
  mediaType,
  showHulls = true,
  showCentroids = true,
  showBoxes = true,
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    if (mediaType === 'IMAGE') {
      const img = new Image();
      img.crossOrigin = 'anonymous';
      img.src = mediaUrl;
      img.onload = () => {
        canvas.width = img.width;
        canvas.height = img.height;
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.drawImage(img, 0, 0);

        // Render Group Overlays
        result.groups.forEach((group, idx) => {
          const color = CLUSTER_HEX[idx % CLUSTER_HEX.length];

          // Bounding Box
          if (showBoxes && group.bounding_box_json) {
            try {
              const bbox = JSON.parse(group.bounding_box_json);
              const [minX, minY, maxX, maxY] = bbox;
              ctx.strokeStyle = color;
              ctx.lineWidth = 2;
              ctx.strokeRect(minX, minY, maxX - minX, maxY - minY);

              ctx.fillStyle = color;
              ctx.font = '12px Inter, sans-serif';
              ctx.fillText(
                `Group ${group.cluster_id} (n=${group.member_count})`,
                minX,
                Math.max(minY - 5, 12)
              );
            } catch {}
          }

          // Centroid
          if (showCentroids) {
            ctx.fillStyle = color;
            ctx.beginPath();
            ctx.arc(group.centroid_x, group.centroid_y, 4, 0, Math.PI * 2);
            ctx.fill();
            ctx.strokeStyle = '#ffffff';
            ctx.lineWidth = 1.5;
            ctx.stroke();
          }
        });
      };
    }
  }, [mediaUrl, result, mediaType, showHulls, showCentroids, showBoxes]);

  return (
    <div className="relative rounded-xl overflow-hidden border border-slate-700 bg-slate-950 flex items-center justify-center min-h-[300px]">
      {mediaType === 'IMAGE' ? (
        <canvas ref={canvasRef} className="max-w-full h-auto object-contain" />
      ) : (
        <video
          src={mediaUrl}
          controls
          className="max-w-full h-auto object-contain"
        />
      )}
    </div>
  );
};
