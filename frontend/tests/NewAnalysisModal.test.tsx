import { render,screen,fireEvent,cleanup } from '@testing-library/react';
import { afterEach,describe,it,expect } from 'vitest';
import { NewAnalysisModal } from '../src/features/analysis/NewAnalysisModal';
import { AnalysisSession,MediaAsset } from '../src/types/api';

afterEach(cleanup);
describe('Detection threshold guidance', () => {
  it('explains a strict filter and offers an explicit reset to the recommended score', () => {
    render(<NewAnalysisModal session={{id:'s',title:'Test'} as AnalysisSession}
      initialMedia={{id:'m',media_type:'VIDEO',original_filename:'clip.mp4'} as MediaAsset}
      onJobStarted={() => {}} onClose={() => {}} />);
    const slider=screen.getByRole('slider',{name:'Minimum detection score'});
    expect(slider).toHaveValue('0.25');
    fireEvent.change(slider,{target:{value:'0.9'}});
    expect(screen.getByRole('alert')).toHaveTextContent('can remove every detection');
    fireEvent.click(screen.getByRole('button',{name:'Use recommended 25% minimum score'}));
    expect(slider).toHaveValue('0.25');
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });
});
