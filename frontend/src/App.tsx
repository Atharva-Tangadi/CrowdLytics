import React from 'react';
import { Activity, ShieldCheck, Cpu } from 'lucide-react';

export const App: React.FC = () => {
  return (
    <div className="min-h-screen bg-slate-900 text-white flex flex-col items-center justify-center p-6">
      <header className="max-w-3xl text-center space-y-4">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 text-sm font-medium">
          <Activity className="w-4 h-4" /> System Online & Ready
        </div>
        <h1 className="text-4xl sm:text-5xl font-extrabold tracking-tight bg-gradient-to-r from-emerald-400 via-teal-300 to-cyan-400 bg-clip-text text-transparent">
          Aerial Crowd Intelligence
        </h1>
        <p className="text-slate-400 text-base sm:text-lg">
          Hierarchical Clustering-Based Spatial Grouping, Closeness Estimation, and Collective Movement Analysis
        </p>
      </header>

      <main className="mt-10 grid grid-cols-1 md:grid-cols-2 gap-6 max-w-3xl w-full">
        <div className="p-6 bg-slate-800/60 rounded-xl border border-slate-700/60 shadow-lg space-y-2">
          <div className="flex items-center gap-3">
            <Cpu className="w-5 h-5 text-emerald-400" />
            <h2 className="text-lg font-semibold">Core Analytics Engine</h2>
          </div>
          <p className="text-sm text-slate-400">
            High-altitude aerial localization, SciPy agglomerative clustering, convex hull closeness, and optical flow motion vector dynamics.
          </p>
        </div>

        <div className="p-6 bg-slate-800/60 rounded-xl border border-slate-700/60 shadow-lg space-y-2">
          <div className="flex items-center gap-3">
            <ShieldCheck className="w-5 h-5 text-cyan-400" />
            <h2 className="text-lg font-semibold">Secure Operations</h2>
          </div>
          <p className="text-sm text-slate-400">
            Tenant isolation, encrypted token authentication, private media storage, and server-side authorization on all endpoints.
          </p>
        </div>
      </main>
    </div>
  );
};

export default App;
