import { describe, it, expect } from 'vitest';
import { matchingFrame, details } from '../src/features/analysis/annotations';
import { FrameAnnotation } from '../src/types/api';

const frame = (timestamp: number, end: number): FrameAnnotation => ({
  timestamp, valid_until: end, crowd_count: 3, confidence: .9, frame_index: 1, groups: [],
});
describe('Causal overlay selection', () => {
  it('never selects future, expired or unrelated annotations', () => {
    const frames = [frame(1,1.2),frame(2,2.2)];
    expect(matchingFrame(frames,.99)).toBeNull();
    expect(matchingFrame(frames,1.1)?.timestamp).toBe(1);
    expect(matchingFrame(frames,1.2)).toBeNull();
    expect(matchingFrame(frames,1.99)).toBeNull();
    expect(matchingFrame(frames,2)?.timestamp).toBe(2);
    expect(matchingFrame(frames,3)).toBeNull();
    expect(matchingFrame([],2)).toBeNull();
  });
  it('tolerates legacy results', () => { expect(details(null)).toEqual({}); });
});
