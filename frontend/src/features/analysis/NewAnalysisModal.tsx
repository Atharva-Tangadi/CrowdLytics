import React, { useState } from 'react';
import { Upload, Video, Image as ImageIcon, Sliders, Play, AlertCircle, Ellipsis } from 'lucide-react';
import { api } from '../../services/api';
import { AnalysisSession, MediaAsset, AnalysisJob } from '../../types/api';

interface NewAnalysisModalProps {
  session: AnalysisSession;
  initialMedia?: MediaAsset | null;
  onJobStarted: (job: AnalysisJob) => void;
  onClose: () => void;
}

export const NewAnalysisModal: React.FC<NewAnalysisModalProps> = ({
  session,
  initialMedia,
  onJobStarted,
  onClose,
}) => {
  const [, setFile] = useState<File | null>(null);
  const [mediaAsset, setMediaAsset] = useState<MediaAsset | null>(initialMedia || null);
  const [uploading, setUploading] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Analytical Parameters
  const [detector, setDetector] = useState<'person' | 'blob'>('person');
  const [grouping, setGrouping] = useState<'density' | 'hac'>('density');
  const [confThresh, setConfThresh] = useState(0.25);
  const [distThresh, setDistThresh] = useState(50.0);
  const [cameraMode, setCameraMode] = useState<'auto' | 'static'>('static');
  const [minIncrease, setMinIncrease] = useState(15);
  const [minPercent, setMinPercent] = useState(50);
  const [persistence, setPersistence] = useState(1);
  const [windowSeconds, setWindowSeconds] = useState(10);
  const [eventsEnabled, setEventsEnabled] = useState(true);
  const [linkage, setLinkage] = useState<'ward' | 'complete' | 'average'>('ward');

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const selected = e.target.files[0];
      setFile(selected);
      setError(null);
      setUploading(true);
      try {
        const asset = await api.uploadMedia(session.id, selected);
        setMediaAsset(asset);
      } catch (err: any) {
        setError(err.message || 'Media upload failed');
      } finally {
        setUploading(false);
      }
    }
  };

  const handleStartAnalysis = async () => {
    if (!mediaAsset) return;
    setAnalyzing(true);
    setError(null);
    try {
      const job = await api.startAnalysis(session.id, {
        media_asset_id: mediaAsset.id,
        detector_backend: detector,
        clustering_method: grouping,
        confidence_threshold: confThresh,
        distance_threshold: distThresh,
        linkage_method: linkage,
        sample_interval_frames: 5,
        camera_mode: cameraMode,
        crowd_increase: { enabled: eventsEnabled, min_absolute: minIncrease, min_percent: minPercent,
          persistence_seconds: persistence, window_seconds: windowSeconds },
      });
      onJobStarted(job);
    } catch (err: any) {
      setError(err.message || 'Failed to start analysis job');
      setAnalyzing(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
      <div className="w-full max-w-xl max-h-[90vh] overflow-y-auto bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-2xl space-y-6">
        <div className="flex items-center justify-between border-b border-slate-800 pb-4">
          <div>
            <h2 className="text-lg font-bold text-white">Start New Crowd Analysis</h2>
            <p className="text-xs text-slate-400">Session: {session.title}</p>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-white text-sm"
          >
            ✕
          </button>
        </div>

        {error && (
          <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-xl text-red-400 text-xs flex items-center gap-2">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* Upload Dropzone */}
        {!mediaAsset ? (
          <label className="border-2 border-dashed border-slate-700 hover:border-emerald-500 rounded-xl p-8 flex flex-col items-center justify-center cursor-pointer transition-colors bg-slate-800/40">
            <input
              type="file"
              accept="image/png,image/jpeg,video/mp4"
              onChange={handleFileChange}
              disabled={uploading}
              className="hidden"
            />
            <Upload className="w-8 h-8 text-emerald-400 mb-2" />
            <span className="text-sm font-medium text-white">
              {uploading ? 'Validating & Uploading...' : 'Upload Aerial Photograph or Video'}
            </span>
            <span className="text-xs text-slate-400 mt-1">
              Supports JPEG, PNG, or MP4 drone video
            </span>
          </label>
        ) : (
          <div className="p-4 rounded-xl bg-slate-800/80 border border-slate-700 flex items-center justify-between">
            <div className="flex items-center gap-3">
              {mediaAsset.media_type === 'IMAGE' ? (
                <ImageIcon className="w-6 h-6 text-emerald-400" />
              ) : (
                <Video className="w-6 h-6 text-purple-400" />
              )}
              <div>
                <div className="text-sm font-medium text-white">
                  {mediaAsset.original_filename}
                </div>
                <div className="text-xs text-slate-400">
                  {mediaAsset.media_type} • {mediaAsset.width}x{mediaAsset.height} px
                  {mediaAsset.duration_seconds
                    ? ` • ${mediaAsset.duration_seconds.toFixed(1)}s`
                    : ''}
                </div>
              </div>
            </div>
            <button
              onClick={() => {
                setFile(null);
                setMediaAsset(null);
              }}
              className="text-xs text-slate-400 hover:text-red-400"
            >
              Change
            </button>
          </div>
        )}

        {/* Parameter Configuration */}
        <details>
          <summary aria-label="Additional settings" title="Additional settings" className="ml-auto flex h-9 w-9 cursor-pointer list-none items-center justify-center rounded-lg border border-slate-700 text-slate-400 hover:bg-slate-800 hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-emerald-500 [&::-webkit-details-marker]:hidden">
            <Ellipsis className="h-5 w-5" aria-hidden="true" />
          </summary>
          <div className="mt-3 space-y-5 rounded-xl border border-slate-700 bg-slate-900/50 p-4">
        <div className="space-y-4">
          <label className="block text-xs">Detector <select aria-label="Detector" className="bg-slate-800 p-2 ml-2" value={detector} onChange={e => setDetector(e.target.value as 'person'|'blob')}>
            <option value="person">Overhead person model (local)</option><option value="blob">Synthetic blob demo only</option>
          </select></label>
          <label className="block text-xs">Grouping <select aria-label="Grouping" className="bg-slate-800 p-2 ml-2" value={grouping} onChange={e => setGrouping(e.target.value as 'density'|'hac')}>
            <option value="density">Spatial neighborhoods (persistent members)</option><option value="hac">Hierarchical clustering (HAC)</option>
          </select></label>
          <p className="text-xs text-slate-400">The learned model estimates visible people. A 90% threshold discards most difficult detections; start at 25%. Reanalysis replaces the displayed run while retaining previous data.</p>
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-slate-400">
            <Sliders className="w-4 h-4 text-emerald-400" /> Analysis Parameters
          </div>

          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1">
                Minimum score: {(confThresh * 100).toFixed(0)}%
              </label>
              <input
                type="range"
                aria-label="Minimum detection score"
                min="0.1"
                max="0.9"
                step="0.05"
                value={confThresh}
                onChange={(e) => setConfThresh(parseFloat(e.target.value))}
                className="w-full accent-emerald-500"
              />
              <span className="text-[10px] text-slate-500">
                Filter only; this is not model accuracy
              </span>
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1">
                Distance: {distThresh} px
              </label>
              <input
                type="range"
                min="10"
                max="200"
                step="5"
                value={distThresh}
                onChange={(e) => setDistThresh(parseFloat(e.target.value))}
                className="w-full accent-emerald-500"
              />
              <span className="text-[10px] text-slate-500">
                Cluster cutoff distance
              </span>
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1">
                Linkage Criterion
              </label>
              <select
                disabled={grouping !== 'hac'}
                value={linkage}
                onChange={(e) => setLinkage(e.target.value as any)}
                className="w-full px-3 py-1.5 bg-slate-800 border border-slate-700 rounded-lg text-xs text-white focus:outline-none focus:border-emerald-500"
              >
                <option value="ward">Ward's (Variance Minimum)</option>
                <option value="complete">Complete (Maximum Distance)</option>
                <option value="average">Average Linkage</option>
              </select>
              <span className="text-[10px] text-slate-500">
                Used only in hierarchical grouping mode
              </span>
            </div>
          </div>
          {detector === 'person' && confThresh > .6 && <div role="alert" className="p-3 rounded bg-amber-500/10 text-amber-200 text-xs space-y-2">
            <p>A {(confThresh*100).toFixed(0)}% minimum score can remove every detection. Increasing this value does not improve the model's accuracy.</p>
            <button className="underline" onClick={() => setConfThresh(.25)}>Use recommended 25% minimum score</button>
          </div>}
        </div>

        {mediaAsset?.media_type === 'VIDEO' && <fieldset className="space-y-3 text-xs border-t border-slate-700 pt-3">
          <legend>Video motion and crowd increase</legend>
          <label className="block">Camera mode <select aria-label="Camera mode" value={cameraMode}
            onChange={e => setCameraMode(e.target.value as 'auto' | 'static')} className="bg-slate-800 ml-2 p-2">
            <option value="auto">Auto (validate and compensate drift)</option>
            <option value="static">Static drone (fixed monitored scene)</option>
          </select></label>
          <label className="block"><input type="checkbox" checked={eventsEnabled} onChange={e => setEventsEnabled(e.target.checked)} /> Detect sudden crowd increases</label>
          <div className="grid grid-cols-2 gap-3">
            <label>Minimum increase (people)<input aria-label="Minimum increase" className="block bg-slate-800 w-full p-2" type="number" min="1" max="10000" value={minIncrease} onChange={e => setMinIncrease(Number(e.target.value))} /></label>
            <label>Minimum increase (%)<input aria-label="Minimum percentage" className="block bg-slate-800 w-full p-2" type="number" min="0" max="10000" value={minPercent} onChange={e => setMinPercent(Number(e.target.value))} /></label>
            <label>Persistence (seconds)<input aria-label="Persistence" className="block bg-slate-800 w-full p-2" type="number" min="0" max="30" step="0.5" value={persistence} onChange={e => setPersistence(Number(e.target.value))} /></label>
            <label>Baseline window (seconds)<input aria-label="Baseline window" className="block bg-slate-800 w-full p-2" type="number" min="4" max="120" value={windowSeconds} onChange={e => setWindowSeconds(Number(e.target.value))} /></label>
          </div>
          <p className="text-slate-400">Speed is in px/s. Directions are image-relative. Count increases are not proof of an organized flash mob. Baseline needs at least 3 seconds of valid history.</p>
        </fieldset>}
          </div>
        </details>
        {/* Action Controls */}
        <div className="flex justify-end gap-3 pt-4 border-t border-slate-800">
          <button
            onClick={onClose}
            className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-xs font-medium"
          >
            Cancel
          </button>
          <button
            onClick={handleStartAnalysis}
            disabled={!mediaAsset || analyzing}
            className="px-5 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-xs font-medium flex items-center gap-2 disabled:opacity-50 shadow-lg shadow-emerald-900/30"
          >
            <Play className="w-3.5 h-3.5" />
            {analyzing ? 'Dispatching...' : 'Launch Intelligence Pipeline'}
          </button>
        </div>
      </div>
    </div>
  );
};
