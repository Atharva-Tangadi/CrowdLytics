import { render, screen, cleanup } from '@testing-library/react';
import { afterEach, describe, it, expect } from 'vitest';
import { VideoAnalytics } from '../src/features/analysis/VideoAnalytics';
import { FrameAnnotation } from '../src/types/api';

afterEach(cleanup);
const frames: FrameAnnotation[] = [
  {timestamp:0,valid_until:1,frame_index:0,crowd_count:10,confidence:.8,groups:[]},
  {timestamp:1,valid_until:2,frame_index:5,crowd_count:15,confidence:.8,groups:[]},
];
describe('Playback analytics', () => {
  it('updates the prominent count with playback and does not substitute the final count in gaps', () => {
    const {rerender} = render(<VideoAnalytics frame={frames[0]} frames={frames} time={0} seek={() => {}} />);
    expect(screen.getByTestId('live-count')).toHaveTextContent('10');
    rerender(<VideoAnalytics frame={frames[1]} frames={frames} time={1} seek={() => {}} />);
    expect(screen.getByTestId('live-count')).toHaveTextContent('15');
    rerender(<VideoAnalytics frame={null} frames={frames} time={3} seek={() => {}} />);
    expect(screen.getByTestId('live-count')).toHaveTextContent('Unavailable');
    expect(screen.getByRole('img',{name:/Visible people over time/})).toBeInTheDocument();
  });
});
