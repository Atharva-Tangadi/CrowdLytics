import React from 'react';
import { AnalysisResult } from '../../types/api';
import { Users, Network, Maximize2, Compass, Activity, Download } from 'lucide-react';
import { api } from '../../services/api';

export const MetricsOverview: React.FC<{ sessionId: string; result: AnalysisResult }> = ({
  sessionId,
  result,
}) => {
  return (
    <div className="space-y-6">
      {/* Metric Cards Grid */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="p-4 rounded-xl bg-slate-800/80 border border-slate-700/80">
          <div className="flex items-center gap-2 text-slate-400 text-xs mb-1">
            <Users className="w-4 h-4 text-emerald-400" /> Total Crowd Count
          </div>
          <div className="text-2xl font-bold text-white">{result.total_crowd_count}</div>
          <div className="text-[11px] text-emerald-400 mt-1">
            Confidence: {(result.confidence_score * 100).toFixed(0)}%
          </div>
        </div>

        <div className="p-4 rounded-xl bg-slate-800/80 border border-slate-700/80">
          <div className="flex items-center gap-2 text-slate-400 text-xs mb-1">
            <Network className="w-4 h-4 text-cyan-400" /> Spatial Clusters (HAC)
          </div>
          <div className="text-2xl font-bold text-white">{result.cluster_count}</div>
          <div className="text-[11px] text-slate-400 mt-1">
            Agglomerative groups
          </div>
        </div>

        <div className="p-4 rounded-xl bg-slate-800/80 border border-slate-700/80">
          <div className="flex items-center gap-2 text-slate-400 text-xs mb-1">
            <Maximize2 className="w-4 h-4 text-amber-400" /> Mean Closeness (NN)
          </div>
          <div className="text-2xl font-bold text-white">
            {result.mean_closeness_px.toFixed(1)}{' '}
            <span className="text-xs font-normal text-slate-400">px</span>
          </div>
          <div className="text-[11px] text-slate-400 mt-1">
            1-Nearest Neighbor distance
          </div>
        </div>

        <div className="p-4 rounded-xl bg-slate-800/80 border border-slate-700/80">
          <div className="flex items-center gap-2 text-slate-400 text-xs mb-1">
            <Compass className="w-4 h-4 text-purple-400" /> Collective Direction
          </div>
          <div className="text-2xl font-bold text-white">
            {result.dominant_direction_deg !== null ? (
              `${result.dominant_direction_deg.toFixed(1)}°`
            ) : (
              <span className="text-sm font-normal text-slate-500">N/A (Still Image)</span>
            )}
          </div>
          <div className="text-[11px] text-slate-400 mt-1">
            {result.dominant_formation_type ? `Formation: ${result.dominant_formation_type}` : 'Zero motion hallucination'}
          </div>
        </div>
      </div>

      {/* Cluster Details Table */}
      <div className="rounded-xl bg-slate-800/80 border border-slate-700/80 p-5">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Activity className="w-5 h-5 text-emerald-400" />
            <h3 className="text-base font-semibold text-white">Group-Level Hierarchy Details</h3>
          </div>
          <div className="flex gap-2">
            <a
              href={api.getExportUrl(sessionId, 'json')}
              download
              className="px-3 py-1.5 rounded-lg bg-slate-700 hover:bg-slate-600 text-slate-200 text-xs font-medium flex items-center gap-1.5 transition-colors"
            >
              <Download className="w-3.5 h-3.5" /> Export JSON
            </a>
            <a
              href={api.getExportUrl(sessionId, 'csv')}
              download
              className="px-3 py-1.5 rounded-lg bg-slate-700 hover:bg-slate-600 text-slate-200 text-xs font-medium flex items-center gap-1.5 transition-colors"
            >
              <Download className="w-3.5 h-3.5" /> Export CSV
            </a>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-900/60 text-slate-400 uppercase tracking-wider text-[10px]">
              <tr>
                <th className="px-4 py-2.5">Cluster ID</th>
                <th className="px-4 py-2.5">Members</th>
                <th className="px-4 py-2.5">Centroid (X, Y)</th>
                <th className="px-4 py-2.5">Convex Hull Area</th>
                <th className="px-4 py-2.5">Mean NN Distance</th>
                <th className="px-4 py-2.5">Density (/kpx²)</th>
                <th className="px-4 py-2.5">State / Dynamics</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-700/60 text-slate-300">
              {result.groups.map((group) => (
                <tr key={group.id} className="hover:bg-slate-700/30">
                  <td className="px-4 py-2.5 font-medium text-white">Group {group.cluster_id}</td>
                  <td className="px-4 py-2.5">{group.member_count}</td>
                  <td className="px-4 py-2.5">
                    ({group.centroid_x.toFixed(1)}, {group.centroid_y.toFixed(1)})
                  </td>
                  <td className="px-4 py-2.5">
                    {group.convex_hull_area > 0
                      ? `${group.convex_hull_area.toFixed(1)} px²`
                      : 'Collinear (0)'}
                  </td>
                  <td className="px-4 py-2.5">{group.mean_nn_distance.toFixed(1)} px</td>
                  <td className="px-4 py-2.5">{group.density_per_kpx.toFixed(2)}</td>
                  <td className="px-4 py-2.5">
                    <span className="px-2 py-0.5 rounded-full bg-slate-700 text-[10px] text-slate-300">
                      {group.formation_state || 'Stable'}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
