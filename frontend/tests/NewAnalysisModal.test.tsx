import { render,screen,fireEvent,cleanup } from '@testing-library/react';
import { afterEach,describe,it,expect } from 'vitest';
import { NewAnalysisModal } from '../src/features/analysis/NewAnalysisModal';
import { AnalysisSession,MediaAsset } from '../src/types/api';

afterEach(cleanup);
describe('Detection threshold guidance', () => {
  it('lets the user select aerial or CCTV inference modes', () => {
    render(<NewAnalysisModal session={{id:'s',title:'Test'} as AnalysisSession}
      initialMedia={{id:'m',media_type:'IMAGE',original_filename:'crowd.png'} as MediaAsset}
      onJobStarted={() => {}} onClose={() => {}} />);
    const mode=screen.getByRole('combobox',{name:'Detection mode'});
    expect(mode).toHaveValue('aerial');
    fireEvent.change(mode,{target:{value:'cctv'}});
    expect(mode).toHaveValue('cctv');
    expect(screen.getByText('python scripts/setup_cctv_model.py')).toBeInTheDocument();
  });

  it('explains that thresholds require labelled validation', () => {
    render(<NewAnalysisModal session={{id:'s',title:'Test'} as AnalysisSession}
      initialMedia={{id:'m',media_type:'VIDEO',original_filename:'clip.mp4'} as MediaAsset}
      onJobStarted={() => {}} onClose={() => {}} />);
    const slider=screen.getByRole('slider',{name:'Minimum detection score'});
    expect(slider).toHaveValue('0.25');
    fireEvent.change(slider,{target:{value:'0.9'}});
    expect(screen.getByRole('alert')).toHaveTextContent('Lowering it can add false positives');
    expect(screen.getByRole('alert')).toHaveTextContent('labelled images');
  });
});
