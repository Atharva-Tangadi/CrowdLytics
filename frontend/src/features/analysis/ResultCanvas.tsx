import React, { useRef, useEffect, useState, useMemo, useCallback } from 'react';
import { AnalysisResult, AnalysisChunk, FrameAnnotation, PersonDetectionAnnotation } from '../../types/api';
import { details, matchingFrame } from './annotations';
import { VideoAnalytics } from './VideoAnalytics';

interface ResultCanvasProps {
  mediaUrl: string;
  jobId?: string;
  result?: AnalysisResult | null;
  chunks?: AnalysisChunk[];
  mediaType: 'IMAGE' | 'VIDEO';
  isAnalyzing?: boolean;
  showHulls?: boolean;
  showCentroids?: boolean;
  showBoxes?: boolean;
}
const COLORS = ['#ef4444','#3b82f6','#10b981','#f59e0b','#a855f7','#ec4899','#06b6d4','#eab308'];

export const ResultCanvas: React.FC<ResultCanvasProps> = ({ mediaUrl, jobId, result, chunks = [], mediaType,
  isAnalyzing = false, showHulls = true, showCentroids = true, showBoxes = true }) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const waitingCoverage = useRef<number | null>(null);
  const [buffering,setBuffering] = useState(false);
  const [visible, setVisible] = useState(true);
  const [hulls, setHulls] = useState(showHulls);
  const [centroids, setCentroids] = useState(showCentroids);
  const [arrows, setArrows] = useState(true);
  const [speeds, setSpeeds] = useState(true);
  const [events, setEvents] = useState(true);
  const [personBoxes, setPersonBoxes] = useState(true);
  const [detailed, setDetailed] = useState(false);
  const [arrowLength, setArrowLength] = useState(36);
  const [time, setTime] = useState(0);
  const [frameData, setFrameData] = useState<FrameAnnotation | null>(null);
  const summary = useMemo(() => details(result), [result]);
  const imageDetectionCount = summary.detection_count ?? summary.detections?.length ?? result?.total_crowd_count ?? 0;
  const frames = useMemo(() => {
    const values: FrameAnnotation[] = [];
    for (const chunk of chunks) {
      try { values.push(...JSON.parse(chunk.frame_data_json)); } catch { /* Ignore malformed legacy chunks. */ }
    }
    return values.sort((a,b) => a.timestamp - b.timestamp);
  }, [chunks]);

  const draw = useCallback((image?: HTMLImageElement) => {
    const canvas = canvasRef.current;
    const video = videoRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    const width=image?.naturalWidth || video?.videoWidth || 640;
    const height=image?.naturalHeight || video?.videoHeight || 360;
    if (canvas.width!==width) canvas.width=width;
    if (canvas.height!==height) canvas.height=height;
    ctx.clearRect(0,0,canvas.width,canvas.height);
    if (image) ctx.drawImage(image,0,0);
    let playbackTime=video?.currentTime || 0;
    if (video?.ended) playbackTime=Math.max(0,playbackTime-.0001);
    const current = mediaType === 'VIDEO' ? matchingFrame(frames, playbackTime) : null;
    if (video && isAnalyzing && !current && !video.paused) {
      video.pause();
      waitingCoverage.current=frames[frames.length-1]?.valid_until || 0;
      setBuffering(true);
    }
    if (mediaType === 'VIDEO') {
      setFrameData(current);
      setTime(video?.currentTime || 0);
    }
    if (!visible) return;
    const detections: PersonDetectionAnnotation[] = mediaType === 'VIDEO'
      ? current?.detections || [] : summary.detections || [];
    if (personBoxes) detections.forEach(detection => {
      const [x1, y1, x2, y2] = detection.bbox || [
        detection.center[0] - 4, detection.center[1] - 4,
        detection.center[0] + 4, detection.center[1] + 4,
      ];
      ctx.strokeStyle = '#fb923c';
      ctx.lineWidth = 2;
      ctx.strokeRect(x1, y1, Math.max(x2 - x1, 1), Math.max(y2 - y1, 1));
      const label = `${(detection.confidence * 100).toFixed(0)}%`;
      ctx.font = 'bold 11px sans-serif';
      ctx.fillStyle = '#0f172add';
      ctx.fillRect(x1, Math.max(0, y1 - 16), ctx.measureText(label).width + 6, 15);
      ctx.fillStyle = '#fdba74';
      ctx.fillText(label, x1 + 3, Math.max(11, y1 - 4));
    });
    const groups = mediaType === 'VIDEO' ? current?.groups || [] : (result?.groups || []).map(g => ({
      ...g, group_id: g.cluster_id, centroid: [g.centroid_x,g.centroid_y],
      bounding_box: JSON.parse(g.bounding_box_json),
      convex_hull: summary.group_annotations?.find(a => a.cluster_id === g.cluster_id)?.convex_hull,
      direction_label: 'Unavailable for still image', mean_nn_distance: g.mean_nn_distance,
    }));
    groups.forEach((g) => {
      const color = COLORS[(g.group_id - 1) % COLORS.length];
      const [cx,cy] = g.centroid;
      ctx.strokeStyle = color;
      ctx.lineWidth = 2;
      if (hulls && g.convex_hull && g.convex_hull.length >= 3) {
        ctx.beginPath();
        g.convex_hull.forEach(([x,y],i) => i ? ctx.lineTo(x,y) : ctx.moveTo(x,y));
        ctx.closePath(); ctx.fillStyle = color + '33'; ctx.fill(); ctx.stroke();
      }
      if (showBoxes && (mediaType === 'IMAGE' || !g.convex_hull || g.convex_hull.length < 3)) {
        const [x1,y1,x2,y2] = g.bounding_box;
        ctx.strokeStyle=color; ctx.strokeRect(x1-4,y1-4,Math.max(x2-x1,4)+8,Math.max(y2-y1,4)+8);
      }
      if (centroids) {
        ctx.beginPath(); ctx.arc(cx,cy,5,0,Math.PI*2); ctx.fillStyle=color; ctx.fill();
        ctx.strokeStyle='#fff'; ctx.stroke();
      }
      if (mediaType === 'VIDEO' && arrows && g.motion_angle_deg != null && g.motion_speed != null && g.motion_speed > 0) {
        // Version 1 used clockwise angles. Version 2 uses mathematical image-relative angles.
        const rad = g.motion_angle_deg * Math.PI / 180 * ((current?.annotation_version || 1) >= 2 ? -1 : 1);
        const ex = cx + Math.cos(rad)*arrowLength, ey = cy + Math.sin(rad)*arrowLength;
        ctx.strokeStyle='#facc15'; ctx.beginPath(); ctx.moveTo(cx,cy); ctx.lineTo(ex,ey); ctx.stroke();
        ctx.beginPath(); ctx.moveTo(ex,ey);
        ctx.lineTo(ex-9*Math.cos(rad-.5),ey-9*Math.sin(rad-.5));
        ctx.lineTo(ex-9*Math.cos(rad+.5),ey-9*Math.sin(rad+.5));
        ctx.closePath(); ctx.fillStyle='#facc15'; ctx.fill();
      }
      const speed = mediaType === 'VIDEO' && speeds ? (g.motion_speed == null ? ' | '+g.direction_label :
        ' | '+g.motion_speed.toFixed(1)+((current?.annotation_version || 1) >= 2 ? ' px/s' : ' px/sample (legacy)')) : '';
      const direction = mediaType === 'VIDEO' && g.motion_angle_deg != null ? ' '+g.direction_label : '';
      const label = `G${g.group_id} (n=${g.member_count})${direction}${speed}`;
      const x = Math.max(6,Math.min(g.bounding_box[0],canvas.width-30));
      const y = Math.max(20,g.bounding_box[1]-12);
      ctx.font='bold 12px sans-serif'; ctx.fillStyle='#0f172add';
      ctx.fillRect(x-3,y-14,ctx.measureText(label).width+6,19);
      ctx.fillStyle=color; ctx.fillText(label,x,y);
      if (detailed) {
        ctx.fillStyle='#fff'; ctx.fillText(`NN: ${g.mean_nn_distance}px | ${g.formation_state || 'Spatial only'}`,x,y+18);
      }
    });
  }, [mediaType,frames,result,summary,visible,hulls,centroids,arrows,speeds,detailed,arrowLength,showBoxes,isAnalyzing,personBoxes]);

  useEffect(() => {
    let disposed = false;
    if (mediaType === 'IMAGE') {
      const image = new Image();
      image.onload = () => { if (!disposed) draw(image); };
      image.src = mediaUrl;
      return () => { disposed = true; image.onload = null; };
    }
    draw();
    // Draw at browser animation cadence so seeking/playback stays synchronized.
    let request = 0;
    const tick = () => { draw(); request = requestAnimationFrame(tick); };
    request = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(request);
  }, [draw,mediaType,mediaUrl]);

  useEffect(() => { setTime(0); setFrameData(null); waitingCoverage.current=null;setBuffering(false); }, [mediaUrl]);
  useEffect(() => {
    const video=videoRef.current;
    const coverage=frames[frames.length-1]?.valid_until || 0;
    if (video && waitingCoverage.current != null && coverage>waitingCoverage.current && matchingFrame(frames,video.currentTime)) {
      waitingCoverage.current=null;setBuffering(false);video.play().catch(() => {});
    }
  }, [frames]);
  useEffect(() => {
    if (!isAnalyzing) { waitingCoverage.current=null;setBuffering(false); }
  }, [isAnalyzing]);
  const event = frameData?.crowd_event;
  const noCoverage = mediaType === 'VIDEO' && !frameData;
  return <div className="space-y-3">
    {result && (summary.annotation_version || 1) < 3 && <p className="p-3 text-amber-300 bg-slate-800 rounded text-sm">
      This is an older analysis. Use “Reanalyze this media with improved detector” to generate person tracks and the new analytics.
    </p>}
    {buffering && <p className="text-amber-300 text-sm">Playback paused while analysis catches up. It resumes when this segment is ready.</p>}
    <div className="rounded-xl overflow-hidden border border-slate-700 bg-black">
      {mediaType === 'IMAGE' ? <canvas ref={canvasRef} className="block max-w-full h-auto mx-auto" /> :
        <div className="relative w-full">
          <video key={mediaUrl} ref={videoRef} src={mediaUrl} controls playsInline
            onTimeUpdate={() => draw()} onSeeked={() => draw()} onLoadedMetadata={() => draw()}
            className="block w-full h-auto" />
          <canvas ref={canvasRef} className="absolute inset-0 w-full h-full pointer-events-none" />
        </div>}
    </div>
    <div className="flex flex-wrap gap-3 p-3 bg-slate-800 rounded-lg text-xs">
      {([['Overlays',visible,setVisible],['Convex hulls',hulls,setHulls],['Centroids',centroids,setCentroids],
        ['Person boxes and scores',personBoxes,setPersonBoxes],
        ['Direction arrows',arrows,setArrows],['Speed labels',speeds,setSpeeds],['Crowd events',events,setEvents],
        ['Detailed metrics',detailed,setDetailed]] as const).map(([label,value,setter]) =>
        <label key={label} className="flex gap-1 items-center"><input type="checkbox" checked={value}
          onChange={e => setter(e.target.checked)} />{label}</label>)}
      {mediaType === 'VIDEO' && <label>Arrow length (display only): <input aria-label="Arrow length" type="range"
        min="20" max="80" value={arrowLength} onChange={e => setArrowLength(Number(e.target.value))} /></label>}
    </div>
    {mediaType === 'VIDEO' && <VideoAnalytics frame={frameData} frames={frames} time={time} jobId={jobId}
      seek={value => { if (videoRef.current) { videoRef.current.currentTime=value; draw(); } }} />}
    {mediaType === 'IMAGE' ? <p className="text-xs text-slate-400">
      Spatial analysis only. Direction and speed unavailable. Visible detections: {imageDetectionCount}.
    </p> :
      <div className="text-xs text-slate-300 space-y-2">
        <p>{time.toFixed(2)}s | Image-relative directions, not geographic headings. Speed: px/s. Arrows have a fixed display length.</p>
        {noCoverage && <p className="text-amber-300">{isAnalyzing ? 'Buffering analysis for this segment' : 'No valid analysis for this timestamp'}</p>}
        {frameData && <p>Groups: {frameData.groups.length} | Count: {frameData.crowd_count} | Camera: {frameData.camera_status || 'Legacy'}</p>}
        {visible && events && event && <div role="status" className="p-3 rounded bg-slate-800">
          <strong>{event.state === 'DETECTED' ? 'Sudden crowd increase detected' : event.state === 'CANDIDATE' ? 'Potential sudden crowd increase' : event.state}</strong>
          {event.timestamp != null && <span> at {event.timestamp.toFixed(2)}s</span>}
          {event.baseline_count != null && <p>Baseline {event.baseline_count}; current {event.current_count}; increase {event.absolute_increase}
            {event.percentage_increase != null ? ` (${event.percentage_increase.toFixed(1)}%)` : ' (percentage unavailable for zero baseline)'}</p>}
          <p>{event.reason}</p>
        </div>}
      </div>}
  </div>;
};
