import React, { useState, useEffect } from 'react';
import { ResultCanvas } from './features/analysis/ResultCanvas';
import { MetricsOverview } from './features/analysis/MetricsOverview';
import { NewAnalysisModal } from './features/analysis/NewAnalysisModal';
import { AnalysisSession, AnalysisJob, AnalysisRun, AnalysisResult, AnalysisChunk, MediaAsset } from './types/api';
import { api } from './services/api';
import {
  Activity,
  Layers,
  Plus,
  Trash2,
  FolderOpen,
  Loader2,
  Cpu,
} from 'lucide-react';

export const App: React.FC = () => {
  const [sessions, setSessions] = useState<AnalysisSession[]>([]);
  const [activeSession, setActiveSession] = useState<AnalysisSession | null>(null);
  const [activeJob, setActiveJob] = useState<AnalysisJob | null>(null);
  const [runs, setRuns] = useState<AnalysisRun[]>([]);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [runError, setRunError] = useState('');
  const [runLoading, setRunLoading] = useState(false);
  const [activeResult, setActiveResult] = useState<AnalysisResult | null>(null);
  const [activeMedia, setActiveMedia] = useState<MediaAsset | null>(null);
  const [chunks, setChunks] = useState<AnalysisChunk[]>([]);
  const [mediaUrl, setMediaUrl] = useState<string | null>(null);
  const [reanalyzeMedia, setReanalyzeMedia] = useState<MediaAsset | null>(null);
  const [showNewModal, setShowNewModal] = useState(false);
  const [newTitle, setNewTitle] = useState('');
  const [creatingSession, setCreatingSession] = useState(false);

  // Load Sessions
  const refreshSessions = async () => {
    try {
      const data = await api.listSessions();
      setSessions(data);
      if (data.length > 0 && !activeSession) {
        setActiveSession(data[0]);
      }
    } catch (err) {
      console.error(err);
    }
  };

  useEffect(() => {
    refreshSessions();
  }, []);

  // Restore runs independently: an empty newer run never deletes earlier analytics.
  useEffect(() => {
    let disposed = false;
    setActiveJob(null); setActiveResult(null); setChunks([]); setActiveMedia(null); setMediaUrl(null);
    setRuns([]); setSelectedRunId(null); setRunError('');
    if (!activeSession) return;
    api.listSessionJobs(activeSession.id).then(history => {
      if (disposed) return;
      setRuns(history);
      if (history.length) setSelectedRunId(history[0].id);
    }).catch(error => { if (!disposed) setRunError(String(error)); });
    return () => { disposed = true; };
  }, [activeSession?.id]);

  useEffect(() => {
    let disposed = false;
    if (!selectedRunId || !activeSession) { setRunLoading(false); return; }
    setRunLoading(true); setRunError(''); setActiveJob(null); setActiveResult(null); setChunks([]);
    Promise.all([api.getJob(selectedRunId),api.getJobResults(selectedRunId),api.getJobChunks(selectedRunId)])
      .then(([job,result,completed]) => {
        if (disposed || job.session_id !== activeSession.id) return;
        setActiveJob(job); setActiveResult(result); setChunks(completed);
      }).catch(error => { if (!disposed) setRunError(String(error)); })
      .finally(() => { if (!disposed) setRunLoading(false); });
    return () => { disposed = true; };
  }, [selectedRunId,activeSession?.id]);

  useEffect(() => {
    let disposed = false;
    let objectUrl: string | null = null;
    setMediaUrl(null); setActiveMedia(null);
    if (!activeSession) return;
    api.listMedia(activeSession.id).then(async media => {
      const selected = media.find(m => m.id === activeJob?.media_asset_id) ||
        (!activeJob ? media[0] : undefined);
      if (!selected || disposed) return;
      const url = await api.getMediaBlobUrl(selected.id);
      if (disposed) { URL.revokeObjectURL(url); return; }
      objectUrl = url; setActiveMedia(selected); setMediaUrl(url);
    }).catch(console.error);
    return () => { disposed = true; if (objectUrl) URL.revokeObjectURL(objectUrl); };
  }, [activeSession?.id, activeJob?.media_asset_id]);

  useEffect(() => {
    if (!activeJob || !activeSession || activeJob.session_id !== activeSession.id ||
      !['QUEUED','RUNNING'].includes(activeJob.status)) return;
    let disposed = false;
    let busy = false;
    let cursor = -1;
    const poll = async () => {
      if (busy) return;
      busy = true;
      try {
        const updated = await api.getJob(activeJob.id);
        const fresh = await api.getJobChunks(activeJob.id, cursor);
        if (disposed) return;
        if (fresh.length) {
          cursor = Math.max(...fresh.map(c => c.chunk_index));
          setChunks(previous => [...new Map([...previous,...fresh].map(c => [c.id,c])).values()]
            .sort((a,b) => a.chunk_index-b.chunk_index));
        }
        if (updated.status === 'COMPLETED') {
          const res = await api.getJobResults(activeJob.id);
          if (!disposed && res?.job_id === activeJob.id) setActiveResult(res);
          const history = await api.listSessionJobs(activeSession.id);
          if (!disposed) setRuns(history);
        }
        if (!disposed) setActiveJob(updated);
      } catch (error) { console.error(error); }
      finally { busy = false; }
    };
    const timer = setInterval(poll,1500);
    poll();
    return () => { disposed = true; clearInterval(timer); };
  }, [activeJob?.id, activeJob?.status, activeSession?.id]);

  const handleCreateSession = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTitle.trim()) return;
    setCreatingSession(true);
    try {
      const created = await api.createSession(newTitle);
      setNewTitle('');
      await refreshSessions();
      setActiveSession(created);
    } finally {
      setCreatingSession(false);
    }
  };

  const handleDeleteSession = async (id: string) => {
    if (confirm('Delete this analysis session?')) {
      await api.deleteSession(id);
      setActiveSession(null);
      setActiveResult(null);
      refreshSessions();
    }
  };

  const selectedRun=runs.find(run => run.id === selectedRunId);
  const previousWithDetections=runs.find(run => run.media_asset_id === selectedRun?.media_asset_id &&
    run.id !== selectedRunId && run.result_available && (run.peak_count || 0)>0);

  return (
    <div className="min-h-screen bg-slate-950 text-white flex flex-col">
      {/* Top Navbar */}
      <nav className="h-14 border-b border-slate-800 bg-slate-900/60 backdrop-blur-md px-6 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Activity className="w-5 h-5 text-emerald-400" />
          <span className="font-bold text-sm tracking-wide text-white">
            Aerial Crowd Intelligence
          </span>
          <span className="text-[10px] uppercase font-semibold px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            Console
          </span>
        </div>

        <span className="text-xs text-slate-400">Local workspace</span>
      </nav>

      <div className="flex-1 flex overflow-hidden">
        {/* Left Sidebar: Sessions */}
        <aside className="w-64 border-r border-slate-800 bg-slate-900/40 p-4 flex flex-col justify-between">
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
                <Layers className="w-3.5 h-3.5" /> Sessions
              </span>
            </div>

            <form onSubmit={handleCreateSession} className="flex gap-1.5">
              <input
                type="text"
                placeholder="New session title..."
                value={newTitle}
                onChange={(e) => setNewTitle(e.target.value)}
                className="flex-1 px-2.5 py-1.5 bg-slate-800/80 border border-slate-700 rounded-lg text-xs text-white placeholder-slate-500 focus:outline-none focus:border-emerald-500"
              />
              <button
                type="submit"
                disabled={creatingSession || !newTitle.trim()}
                className="p-1.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg disabled:opacity-50"
              >
                <Plus className="w-4 h-4" />
              </button>
            </form>

            <div className="space-y-1 overflow-y-auto max-h-[calc(100vh-220px)]">
              {sessions.map((sess) => (
                <div
                  key={sess.id}
                  onClick={() => setActiveSession(sess)}
                  className={`group flex items-center justify-between px-3 py-2 rounded-lg text-xs cursor-pointer transition-colors ${
                    activeSession?.id === sess.id
                      ? 'bg-emerald-500/10 text-emerald-400 font-medium border border-emerald-500/20'
                      : 'text-slate-400 hover:bg-slate-800/60 hover:text-slate-200'
                  }`}
                >
                  <div className="flex items-center gap-2 truncate">
                    <FolderOpen className="w-3.5 h-3.5 shrink-0" />
                    <span className="truncate">{sess.title}</span>
                  </div>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDeleteSession(sess.id);
                    }}
                    className="opacity-0 group-hover:opacity-100 hover:text-red-400 p-0.5"
                  >
                    <Trash2 className="w-3 h-3" />
                  </button>
                </div>
              ))}
            </div>
          </div>

          <div className="text-[11px] text-slate-500 flex items-center gap-1">
            <Cpu className="w-3.5 h-3.5 text-emerald-400" />
            <span>SciPy HAC • OpenCV Flow</span>
          </div>
        </aside>

        {/* Main Content Area */}
        <main className="flex-1 p-6 overflow-y-auto space-y-6">
          {activeSession ? (
            <>
              {/* Header Bar */}
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-xl font-bold text-white">{activeSession.title}</h2>
                  <p className="text-xs text-slate-400">
                    Created on {new Date(activeSession.created_at).toLocaleString()}
                  </p>
                </div>

                <button
                  onClick={() => { setReanalyzeMedia(null); setShowNewModal(true); }}
                  className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-xs font-medium flex items-center gap-2 shadow-lg shadow-emerald-900/30"
                >
                  <Plus className="w-4 h-4" /> Analyze Media
                </button>
              </div>

              {activeMedia && <button className="text-xs px-3 py-2 bg-slate-800 rounded-lg" onClick={() => {
                setReanalyzeMedia(activeMedia); setShowNewModal(true);
              }}>Reanalyze this media with improved detector</button>}
              {runs.length>0 && <label className="block text-sm">Saved analysis
                <select aria-label="Saved analysis" value={selectedRunId || ''} className="block w-full bg-slate-800 rounded p-2 mt-1"
                  onChange={event => setSelectedRunId(event.target.value)}>
                  {runs.map(run => <option key={run.id} value={run.id}>
                    {run.created_at.replace('T',' ').slice(0,19)} UTC | minimum score {(run.confidence_threshold*100).toFixed(0)}% | peak {run.peak_count ?? 'pending'} | {run.status}
                  </option>)}
                </select>
              </label>}
              {runLoading && <p role="status">Loading saved analytics...</p>}
              {runError && <p role="alert" className="text-red-300">{runError}</p>}
              {selectedRun?.result_available && selectedRun.peak_count === 0 && <div role="alert" className="p-4 rounded-lg bg-amber-500/10 text-amber-200 space-y-2">
                <p>No people passed this run's detection filter. Clusters and motion cannot be formed from zero detections.</p>
                <p>Minimum detection score: {(selectedRun.confidence_threshold*100).toFixed(0)}%. This is a filtering threshold, not accuracy.
                  {selectedRun.confidence_threshold>.6 ? ' A high threshold can reject detections; compare alternatives on labelled images before changing it.' : ' Review the detector and source footage.'}</p>
                {previousWithDetections && <button className="underline" onClick={() => setSelectedRunId(previousWithDetections.id)}>View previous run with detections</button>}
              </div>}
              {/* Job Progress Indicator if running */}
              {activeJob && (activeJob.status === 'QUEUED' || activeJob.status === 'RUNNING') && (
                <div className="p-4 bg-emerald-500/10 border border-emerald-500/20 rounded-xl space-y-2">
                  <div className="flex items-center justify-between text-xs text-emerald-400">
                    <span className="font-semibold flex items-center gap-2">
                      <Loader2 className="w-3.5 h-3.5 animate-spin" /> {activeJob.current_stage}
                    </span>
                    <span>{activeJob.progress_pct}%</span>
                  </div>
                  <div className="w-full h-1.5 bg-slate-800 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-emerald-500 transition-all duration-300"
                      style={{ width: `${activeJob.progress_pct}%` }}
                    />
                  </div>
                </div>
              )}

              {activeJob?.status === 'FAILED' && <p role="alert" className="text-red-400">{activeJob.error_message}</p>}
              {activeJob?.status === 'CANCELLED' && <p className="text-amber-300">Analysis cancelled.</p>}
              {activeJob && ['QUEUED','RUNNING'].includes(activeJob.status) && <button className="text-sm text-red-300"
                onClick={async () => setActiveJob(await api.cancelJob(activeJob.id))}>Cancel analysis</button>}
              {/* Active Media & Synchronized Canvas Player */}
              {mediaUrl && (
                <ResultCanvas
                  jobId={activeJob?.id}
                  mediaUrl={mediaUrl}
                  result={activeResult?.job_id === activeJob?.id && activeJob?.media_asset_id === activeMedia?.id ? activeResult : null}
                  chunks={activeJob?.media_asset_id === activeMedia?.id ? chunks : []}
                  mediaType={activeMedia?.media_type || 'IMAGE'}
                  isAnalyzing={activeJob?.status === 'RUNNING'}
                />
              )}

              {/* Analysis Results Metrics Display */}
              {activeResult && activeMedia?.media_type === 'IMAGE' ? (
                <div className="space-y-6">
                  <MetricsOverview
                    sessionId={activeSession.id}
                    result={activeResult}
                  />
                </div>
              ) : !mediaUrl && (
                <div className="p-12 border border-dashed border-slate-800 rounded-2xl flex flex-col items-center justify-center text-center space-y-3">
                  <Activity className="w-10 h-10 text-slate-600" />
                  <div className="text-sm font-medium text-slate-300">
                    No Analysis Performed in This Session
                  </div>
                  <p className="text-xs text-slate-500 max-w-sm">
                    Upload an aerial photograph or drone video to calculate hierarchical crowd clusters, closeness, and collective movement.
                  </p>
                  <button
                    onClick={() => { setReanalyzeMedia(null); setShowNewModal(true); }}
                    className="mt-2 px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg text-xs font-medium"
                  >
                    Upload Media & Run Pipeline
                  </button>
                </div>
              )}
            </>
          ) : (
            <div className="h-full flex flex-col items-center justify-center text-slate-500 space-y-2">
              <FolderOpen className="w-12 h-12 text-slate-700" />
              <div className="text-sm">Select or create a session to start crowd intelligence.</div>
            </div>
          )}
        </main>
      </div>

      {/* New Analysis Modal */}
      {showNewModal && activeSession && (
        <NewAnalysisModal
          session={activeSession}
          initialMedia={reanalyzeMedia}
          onJobStarted={(job) => {
            setActiveResult(null); setChunks([]); setSelectedRunId(job.id); setActiveJob(job);
            api.listSessionJobs(job.session_id).then(setRuns).catch(error => setRunError(String(error)));
            setShowNewModal(false);
          }}
          onClose={() => setShowNewModal(false)}
        />
      )}
    </div>
  );
};

export default App;
