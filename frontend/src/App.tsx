import React, { useState, useEffect } from 'react';
import { useAuth } from './features/auth/AuthContext';
import { AuthModal } from './features/auth/AuthModal';
import { ResultCanvas } from './features/analysis/ResultCanvas';
import { MetricsOverview } from './features/analysis/MetricsOverview';
import { NewAnalysisModal } from './features/analysis/NewAnalysisModal';
import { AnalysisSession, AnalysisJob, AnalysisResult, AnalysisChunk, MediaAsset } from './types/api';
import { api } from './services/api';
import {
  Activity,
  Layers,
  Plus,
  Trash2,
  LogOut,
  FolderOpen,
  Loader2,
  Cpu,
} from 'lucide-react';

export const App: React.FC = () => {
  const { user, loading: authLoading, logout } = useAuth();
  const [sessions, setSessions] = useState<AnalysisSession[]>([]);
  const [activeSession, setActiveSession] = useState<AnalysisSession | null>(null);
  const [activeJob, setActiveJob] = useState<AnalysisJob | null>(null);
  const [activeResult, setActiveResult] = useState<AnalysisResult | null>(null);
  const [activeMedia, setActiveMedia] = useState<MediaAsset | null>(null);
  const [chunks, setChunks] = useState<AnalysisChunk[]>([]);
  const [mediaUrl, setMediaUrl] = useState<string | null>(null);
  const [showNewModal, setShowNewModal] = useState(false);
  const [newTitle, setNewTitle] = useState('');
  const [creatingSession, setCreatingSession] = useState(false);

  // Load Sessions
  const refreshSessions = async () => {
    if (!user) return;
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
  }, [user]);

  // Load Results and Media for active session
  useEffect(() => {
    if (activeSession) {
      setChunks([]);
      api
        .getResults(activeSession.id)
        .then((res) => {
          setActiveResult(res);
          if (res && res.job_id) {
            api.getJobChunks(res.job_id).then(setChunks).catch(() => {});
          }
          // Fetch media to render canvas
          api.listMedia(activeSession.id).then(async (media) => {
            if (media.length > 0) {
              setActiveMedia(media[0]);
              try {
                const blobUrl = await api.getMediaBlobUrl(media[0].id);
                setMediaUrl(blobUrl);
              } catch {
                setMediaUrl(api.getMediaFileUrl(media[0].id));
              }
            } else {
              setActiveMedia(null);
              setMediaUrl(null);
            }
          });
        })
        .catch(() => {
          setActiveResult(null);
          setActiveMedia(null);
          setMediaUrl(null);
          setChunks([]);
        });
    }
  }, [activeSession]);

  // Poll Active Job & Progressive Chunks
  useEffect(() => {
    let interval: any = null;
    if (activeJob && (activeJob.status === 'QUEUED' || activeJob.status === 'RUNNING')) {
      interval = setInterval(async () => {
        try {
          const updated = await api.getJob(activeJob.id);
          setActiveJob(updated);

          // Progressively fetch completed chunks while running
          try {
            const jobChunks = await api.getJobChunks(activeJob.id);
            if (jobChunks && jobChunks.length > 0) {
              setChunks(jobChunks);
            }
          } catch {}

          if (updated.status === 'COMPLETED') {
            if (activeSession) {
              const res = await api.getResults(activeSession.id);
              setActiveResult(res);
              const media = await api.listMedia(activeSession.id);
              if (media.length > 0) {
                setActiveMedia(media[0]);
                try {
                  const blobUrl = await api.getMediaBlobUrl(media[0].id);
                  setMediaUrl(blobUrl);
                } catch {
                  setMediaUrl(api.getMediaFileUrl(media[0].id));
                }
              }
            }
          }
        } catch {
          clearInterval(interval);
        }
      }, 1500);
    }
    return () => clearInterval(interval);
  }, [activeJob, activeSession]);

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

  if (authLoading) {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center text-slate-400">
        <Loader2 className="w-8 h-8 animate-spin text-emerald-400" />
      </div>
    );
  }

  if (!user) {
    return (
      <div className="min-h-screen bg-slate-950 flex flex-col items-center justify-center p-4">
        <header className="mb-8 text-center space-y-2">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 text-xs font-semibold">
            <Activity className="w-3.5 h-3.5" /> High-Altitude Spatial Intelligence
          </div>
          <h1 className="text-3xl font-extrabold text-white">Aerial Crowd Intelligence</h1>
          <p className="text-slate-400 text-sm max-w-sm">
            Hierarchical clustering-based grouping, closeness estimation, and collective movement dynamics.
          </p>
        </header>
        <AuthModal />
      </div>
    );
  }

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

        <div className="flex items-center gap-4">
          <span className="text-xs text-slate-400">{user.email}</span>
          <button
            onClick={logout}
            className="p-1.5 rounded-lg text-slate-400 hover:text-red-400 hover:bg-slate-800 transition-colors"
            title="Sign out"
          >
            <LogOut className="w-4 h-4" />
          </button>
        </div>
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
                  onClick={() => setShowNewModal(true)}
                  className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-xs font-medium flex items-center gap-2 shadow-lg shadow-emerald-900/30"
                >
                  <Plus className="w-4 h-4" /> Analyze Media
                </button>
              </div>

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

              {/* Active Media & Synchronized Canvas Player */}
              {mediaUrl && (
                <ResultCanvas
                  mediaUrl={mediaUrl}
                  result={activeResult}
                  chunks={chunks}
                  mediaType={activeMedia?.media_type || 'IMAGE'}
                  isAnalyzing={activeJob?.status === 'RUNNING'}
                />
              )}

              {/* Analysis Results Metrics Display */}
              {activeResult ? (
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
                    onClick={() => setShowNewModal(true)}
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
          onJobStarted={(job) => {
            setActiveJob(job);
            setShowNewModal(false);
          }}
          onClose={() => setShowNewModal(false)}
        />
      )}
    </div>
  );
};

export default App;
