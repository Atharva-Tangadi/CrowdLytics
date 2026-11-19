import React from 'react';
import { FrameAnnotation } from '../../types/api';
import { api } from '../../services/api';

interface Props { frame: FrameAnnotation | null; frames: FrameAnnotation[]; time: number; jobId?: string;
  seek: (time: number) => void; }

export const VideoAnalytics: React.FC<Props> = ({frame,frames,time,jobId,seek}) => {
  const [error,setError] = React.useState('');
  const stats = React.useMemo(() => {
    const peak=Math.max(1,...frames.map(f => f.crowd_count));
    const end=frames[frames.length-1]?.valid_until || frames[frames.length-1]?.timestamp || 1;
    const lifetimes=new Map<number,{first:number;last:number;samples:number}>();
    for (const sample of frames) for (const group of sample.groups) {
      const row=lifetimes.get(group.group_id) || {first:sample.timestamp,last:sample.timestamp,samples:0};
      row.last=sample.timestamp;row.samples++;lifetimes.set(group.group_id,row);
    }
    return {peak,end,lifetimes,polyline:frames.map(f => `${f.timestamp/end*800},${110-f.crowd_count/peak*100}`).join(' ')};
  }, [frames]);
  const {peak,end}=stats;
  const exportData = async (format: 'json' | 'csv') => {
    if (!jobId) return;
    try { await api.downloadTimeline(jobId,format); setError(''); }
    catch (e) { setError(String(e)); }
  };
  return <section className="space-y-4 rounded-xl bg-slate-900 border border-slate-700 p-4" aria-label="Video analytics">
    <div className="flex justify-between gap-3 flex-wrap">
      <h3 className="font-semibold">Playback analytics <span className="text-slate-400 text-xs">{time.toFixed(2)}s</span></h3>
      <div className="flex gap-3 text-xs"><button disabled={!jobId || !frames.length} onClick={() => exportData('json')}>Download timeline JSON</button>
        <button disabled={!jobId || !frames.length} onClick={() => exportData('csv')}>Download timeline CSV</button></div>
    </div>
    {error && <p role="alert">{error}</p>}
    {frame?.detection_diagnostics && frame.crowd_count === 0 &&
      (frame.detection_diagnostics.candidates_at_diagnostic_threshold ??
        frame.detection_diagnostics.candidates_at_recommended_threshold ?? 0)>0 && <p role="alert" className="text-amber-200 text-sm">
        The {(100*(frame.detection_diagnostics.requested_threshold || 0)).toFixed(0)}% filter rejected all people in this sample.
        This same model pass found {frame.detection_diagnostics.candidates_at_diagnostic_threshold ??
          frame.detection_diagnostics.candidates_at_recommended_threshold} candidates at {
            (100*(frame.detection_diagnostics.diagnostic_threshold ?? .25)).toFixed(0)}%.
        This is not a recommendation to lower the filter; compare thresholds on labelled images.
      </p>}
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
      {[
        ['People now', frame?.crowd_count ?? 'Unavailable'],
        ['Clusters now', frame?.groups.length ?? 'Unavailable'],
        ['Tracked observations', frame?.tracked_count ?? frame?.crowd_count ?? 'Unavailable'],
        ['Peak visible count', frames.length ? Math.max(...frames.map(f => f.crowd_count)) : 'Unavailable'],
      ].map(([label,value]) => <div key={label} className="bg-slate-800 rounded-lg p-3">
        <p className="text-xs text-slate-400">{label}</p><p className="text-2xl font-bold" data-testid={label === 'People now' ? 'live-count' : undefined}>{value}</p>
      </div>)}
    </div>
    <p className="text-xs text-slate-400">Visible detections at the current timestamp, not unique visitors. Tracked observations may include brief optical-flow predictions, marked below.
      Analyzed samples and group metrics are saved in the local database and restored when this session is reopened.</p>
    <svg viewBox="0 0 800 120" role="img" aria-label="Visible people over time; click to seek" className="w-full h-32 bg-slate-950 rounded cursor-pointer"
      onClick={event => { const rect = event.currentTarget.getBoundingClientRect(); seek(Math.max(0,Math.min(1,(event.clientX-rect.left)/rect.width))*end); }}>
      <polyline fill="none" stroke="#34d399" strokeWidth="2" points={stats.polyline} />
      <line x1={time/end*800} x2={time/end*800} y1="0" y2="120" stroke="#facc15" />
      <text x="6" y="14" fill="#94a3b8" fontSize="11">Count: 0–{peak} | 0–{end.toFixed(1)}s</text>
    </svg>
    <div className="overflow-x-auto"><table className="w-full text-xs text-left">
      <thead className="text-slate-400"><tr>{['Cluster','Members','Direction (image-relative)','Speed','Closeness','Density /1,000 px²','Observation'].map(h => <th key={h} className="p-2">{h}</th>)}</tr></thead>
      <tbody>{frame?.groups.map(g => <tr key={g.group_id} className="border-t border-slate-800">
        <td className="p-2">G{g.group_id}</td><td className="p-2">{g.member_count}</td>
        <td className="p-2">{g.direction_label}</td><td className="p-2">{g.motion_speed == null ? 'Collecting / unavailable' : `${g.motion_speed.toFixed(1)} ${g.speed_unit || 'px/sample'}`}</td>
        <td className="p-2">{g.mean_nn_distance.toFixed(1)} px</td><td className="p-2">{g.density_per_kpx.toFixed(2)}</td>
        <td className="p-2">{g.observation_status || 'DETECTED'}</td></tr>)}</tbody>
    </table></div>
    {frame && !frame.groups.length && <p className="text-amber-300 text-xs">No spatial group at this sample. Check detector selection and grouping distance; isolated detections are still counted.</p>}
    {!frame && <p className="text-amber-300 text-xs">Analysis is unavailable for this playback position. No previous or future count is substituted.</p>}
    <details className="text-xs text-slate-300"><summary>Stored group lifetimes ({stats.lifetimes.size} groups, {frames.length} analyzed samples)</summary>
      <div className="max-h-48 overflow-y-auto mt-2">{[...stats.lifetimes].map(([id,row]) => <p key={id}>
        G{id}: {row.first.toFixed(2)}–{row.last.toFixed(2)}s | {row.samples} observations
      </p>)}</div>
    </details>
  </section>;
};
