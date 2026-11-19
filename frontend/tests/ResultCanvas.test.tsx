import { fireEvent, render, screen, cleanup } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ResultCanvas } from '../src/features/analysis/ResultCanvas';
import { AnalysisResult } from '../src/types/api';

const ctx = { clearRect: vi.fn(), drawImage: vi.fn(), strokeRect: vi.fn(), beginPath: vi.fn(),
  moveTo: vi.fn(), lineTo: vi.fn(), closePath: vi.fn(), fill: vi.fn(), stroke: vi.fn(),
  arc: vi.fn(), fillRect: vi.fn(), fillText: vi.fn(), measureText: () => ({width:100}) };
const result = {
  summary_data_json: JSON.stringify({annotation_version:2,group_annotations:[
    {cluster_id:1,convex_hull:[[100,100],[200,100],[150,200]]}]}),
  groups:[{cluster_id:1,member_count:3,centroid_x:150,centroid_y:133,
    bounding_box_json:'[100,100,200,200]',mean_nn_distance:50}],
} as AnalysisResult;

beforeEach(() => {
  vi.spyOn(HTMLCanvasElement.prototype,'getContext').mockReturnValue(ctx as unknown as CanvasRenderingContext2D);
  class FakeImage {
    naturalWidth=1920; naturalHeight=1080;
    onload: (() => void) | null = null;
    set src(_: string) { this.onload?.(); }
  }
  vi.stubGlobal('Image',FakeImage);
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); vi.clearAllMocks(); });

describe('Image cluster overlays', () => {
  it('uses original dimensions and vertices, and displays all visualization controls', () => {
    const {container} = render(<ResultCanvas mediaUrl="blob:image" mediaType="IMAGE" result={result} />);
    expect(container.querySelector('canvas')?.width).toBe(1920);
    expect(container.querySelector('canvas')?.height).toBe(1080);
    expect(ctx.moveTo).toHaveBeenCalledWith(100,100);
    expect(ctx.arc).toHaveBeenCalledWith(150,133,5,0,Math.PI*2);
    expect(screen.getByText(/Direction and speed unavailable/)).toBeInTheDocument();
    for (const label of ['Convex hulls','Centroids','Direction arrows','Speed labels','Crowd events'])
      expect(screen.getByLabelText(label)).toBeChecked();
    ctx.moveTo.mockClear();
    fireEvent.click(screen.getByLabelText('Convex hulls'));
    expect(ctx.moveTo).not.toHaveBeenCalled();
  });
  it('does not invent a hull for legacy image results', () => {
    render(<ResultCanvas mediaUrl="blob:old" mediaType="IMAGE" result={{...result,summary_data_json:null}} />);
    expect(ctx.moveTo).not.toHaveBeenCalled();
    expect(ctx.arc).toHaveBeenCalled();
  });
});
