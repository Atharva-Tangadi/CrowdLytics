import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import App from '../src/App';

describe('App Component', () => {
  it('renders application title and system status', () => {
    render(<App />);
    expect(screen.getByText(/Aerial Crowd Intelligence/i)).toBeInTheDocument();
    expect(screen.getByText(/System Online & Ready/i)).toBeInTheDocument();
  });
});
