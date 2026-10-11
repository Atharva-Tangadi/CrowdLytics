import React, { useState } from 'react';
import { Upload, Video, Image as ImageIcon, Sliders, Play, AlertCircle } from 'lucide-react';
import { api } from '../../services/api';
import { AnalysisSession, MediaAsset, AnalysisJob } from '../../types/api';

interface NewAnalysisModalProps {
  session: AnalysisSession;
  onJobStarted: (job: AnalysisJob) => void;
  onClose: () => void;
}

export const NewAnalysisModal: React.FC<NewAnalysisModalProps> = ({
  session,
  onJobStarted,
  onClose,
}) => {
  const [, setFile] = useState<File | null>(null);
  const [mediaAsset, setMediaAsset] = useState<MediaAsset | null>(null);
  const [uploading, setUploading] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Analytical Parameters
  const [confThresh, setConfThresh] = useState(0.3);
  const [distThresh, setDistThresh] = useState(50.0);
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
        confidence_threshold: confThresh,
        distance_threshold: distThresh,
        linkage_method: linkage,
        sample_interval_frames: 5,
      });
      onJobStarted(job);
    } catch (err: any) {
      setError(err.message || 'Failed to start analysis job');
      setAnalyzing(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
      <div className="w-full max-w-xl bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-2xl space-y-6">
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
        <div className="space-y-4 pt-2 border-t border-slate-800">
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-slate-400">
            <Sliders className="w-4 h-4 text-emerald-400" /> Analysis Parameters
          </div>

          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1">
                Confidence: {(confThresh * 100).toFixed(0)}%
              </label>
              <input
                type="range"
                min="0.1"
                max="0.9"
                step="0.05"
                value={confThresh}
                onChange={(e) => setConfThresh(parseFloat(e.target.value))}
                className="w-full accent-emerald-500"
              />
              <span className="text-[10px] text-slate-500">
                Minimum detector confidence
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
                value={linkage}
                onChange={(e) => setLinkage(e.target.value as any)}
                className="w-full px-3 py-1.5 bg-slate-800 border border-slate-700 rounded-lg text-xs text-white focus:outline-none focus:border-emerald-500"
              >
                <option value="ward">Ward's (Variance Minimum)</option>
                <option value="complete">Complete (Maximum Distance)</option>
                <option value="average">Average Linkage</option>
              </select>
              <span className="text-[10px] text-slate-500">
                Hierarchical clustering criterion
              </span>
            </div>
          </div>
        </div>

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
