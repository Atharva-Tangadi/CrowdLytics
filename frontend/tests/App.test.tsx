import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import App from '../src/App';
import { AuthProvider } from '../src/features/auth/AuthContext';

describe('App & Authentication Flow', () => {
  it('renders authentication screen when unauthenticated', () => {
    render(
      <AuthProvider>
        <App />
      </AuthProvider>
    );
    expect(screen.getAllByText(/Aerial Crowd Intelligence/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/Authenticate/i)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/analyst@domain.com/i)).toBeInTheDocument();
  });
});
