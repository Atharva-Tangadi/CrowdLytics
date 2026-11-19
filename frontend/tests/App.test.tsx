import { render, screen, waitFor, cleanup } from '@testing-library/react';
import { describe, it, expect, vi, afterEach } from 'vitest';
import App from '../src/App';

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe('Local workspace', () => {
  it('opens the dashboard directly and requests sessions without credentials', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ok:true,status:200,json:async () => []});
    vi.stubGlobal('fetch',fetchMock);
    render(<App />);
    expect(screen.getByText('Local workspace')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('New session title...')).toBeInTheDocument();
    expect(screen.queryByText('Authenticate')).not.toBeInTheDocument();
    expect(screen.queryByTitle('Sign out')).not.toBeInTheDocument();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith('/api/v1/sessions', {headers:{}}));
    expect(fetchMock.mock.calls.every(([url]) => !String(url).includes('/auth/'))).toBe(true);
  });
});
