import { render,screen,fireEvent,waitFor,cleanup } from '@testing-library/react';
import { vi,describe,it,expect,afterEach } from 'vitest';
import { api } from '../src/services/api';
import App from '../src/App';
import { AnalysisRun,AnalysisSession,AnalysisResult,MediaAsset,AnalysisChunk } from '../src/types/api';

vi.mock('../src/features/analysis/ResultCanvas', () => ({ResultCanvas: ({jobId,chunks}:{jobId:string;chunks:AnalysisChunk[]}) =>
  <div data-testid="loaded-run">{jobId}:{chunks.length}</div>}));
afterEach(() => { cleanup();vi.restoreAllMocks();vi.unstubAllGlobals(); });

describe('Saved analysis recovery', () => {
  it('reopens the positive historical run instead of requesting the latest zero result again', async () => {
    const history=[{id:'empty',session_id:'s',media_asset_id:'m',status:'COMPLETED',created_at:'2026-11-15T01:00:00',
      confidence_threshold:.9,peak_count:0,result_available:true},
      {id:'working',session_id:'s',media_asset_id:'m',status:'COMPLETED',created_at:'2026-11-14T01:00:00',
        confidence_threshold:.25,peak_count:155,result_available:true}] as AnalysisRun[];
    vi.spyOn(api,'listSessions').mockResolvedValue([{id:'s',title:'Demo',created_at:'2026-11-15T01:00:00'} as AnalysisSession]);
    vi.spyOn(api,'listSessionJobs').mockResolvedValue(history);
    vi.spyOn(api,'getJob').mockImplementation(async id => history.find(r=>r.id===id)!);
    const results=vi.spyOn(api,'getJobResults').mockImplementation(async id => ({id:'r-'+id,job_id:id,media_asset_id:'m',
      total_crowd_count:id==='working'?120:0,confidence_score:.7,cluster_count:0,mean_closeness_px:0,
      mean_density_per_kpx:0,dominant_direction_deg:null,dominant_formation_type:null,
      summary_data_json:'{}',groups:[],created_at:'2026-11-15T01:00:00'} as AnalysisResult));
    vi.spyOn(api,'getJobChunks').mockResolvedValue([{} as AnalysisChunk]);
    vi.spyOn(api,'listMedia').mockResolvedValue([{id:'m',media_type:'VIDEO'} as MediaAsset]);
    vi.spyOn(api,'getMediaBlobUrl').mockResolvedValue('blob:test');
    vi.stubGlobal('URL',class extends URL { static revokeObjectURL=vi.fn(); });
    render(<App />);
    expect(await screen.findByRole('alert')).toHaveTextContent('90%');
    fireEvent.click(await screen.findByRole('button',{name:'View previous run with detections'}));
    await waitFor(() => expect(results).toHaveBeenCalledWith('working'));
    await waitFor(() => expect(screen.getByTestId('loaded-run')).toHaveTextContent('working:1'));
    expect(screen.queryByText(/No people passed this run/)).not.toBeInTheDocument();
  });
});
