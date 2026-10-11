import React, { useState } from 'react';
import { useAuth } from './AuthContext';
import { Activity, Lock, Mail, ArrowRight, ShieldCheck } from 'lucide-react';

export const AuthModal: React.FC<{ onSuccess?: () => void }> = ({ onSuccess }) => {
  const { login, register } = useAuth();
  const [isRegister, setIsRegister] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      if (isRegister) {
        await register(email, password);
      } else {
        await login(email, password);
      }
      onSuccess?.();
    } catch (err: any) {
      setError(err.message || 'Authentication failed');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="w-full max-w-md p-8 bg-slate-800/90 backdrop-blur-md rounded-2xl border border-slate-700/80 shadow-2xl">
      <div className="flex items-center gap-3 mb-6">
        <div className="p-2.5 bg-emerald-500/10 border border-emerald-500/20 rounded-xl text-emerald-400">
          <Activity className="w-6 h-6" />
        </div>
        <div>
          <h2 className="text-xl font-bold text-white">
            {isRegister ? 'Create Account' : 'Authenticate'}
          </h2>
          <p className="text-xs text-slate-400">Aerial Crowd Intelligence System</p>
        </div>
      </div>

      {error && (
        <div className="mb-4 p-3 rounded-lg bg-red-500/10 border border-red-500/30 text-red-400 text-xs">
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-xs font-medium text-slate-300 mb-1.5">Email Address</label>
          <div className="relative">
            <Mail className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="analyst@domain.com"
              className="w-full pl-9 pr-3 py-2 bg-slate-900/80 border border-slate-700 rounded-lg text-sm text-white placeholder-slate-500 focus:outline-none focus:border-emerald-500 transition-colors"
            />
          </div>
        </div>

        <div>
          <label className="block text-xs font-medium text-slate-300 mb-1.5">Password</label>
          <div className="relative">
            <Lock className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
            <input
              type="password"
              required
              minLength={8}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••••••"
              className="w-full pl-9 pr-3 py-2 bg-slate-900/80 border border-slate-700 rounded-lg text-sm text-white placeholder-slate-500 focus:outline-none focus:border-emerald-500 transition-colors"
            />
          </div>
        </div>

        <button
          type="submit"
          disabled={submitting}
          className="w-full mt-2 py-2.5 px-4 bg-emerald-600 hover:bg-emerald-500 text-white font-medium rounded-lg text-sm transition-all flex items-center justify-center gap-2 shadow-lg shadow-emerald-900/20 disabled:opacity-50"
        >
          {submitting ? 'Authenticating...' : isRegister ? 'Register & Enter' : 'Sign In'}
          <ArrowRight className="w-4 h-4" />
        </button>
      </form>

      <div className="mt-6 pt-4 border-t border-slate-700/60 flex items-center justify-between text-xs text-slate-400">
        <span>{isRegister ? 'Already registered?' : 'Need access?'}</span>
        <button
          type="button"
          onClick={() => {
            setIsRegister(!isRegister);
            setError(null);
          }}
          className="text-emerald-400 hover:text-emerald-300 font-medium transition-colors"
        >
          {isRegister ? 'Sign In Instead' : 'Create an Account'}
        </button>
      </div>

      <div className="mt-4 flex items-center gap-1.5 text-[11px] text-slate-500 justify-center">
        <ShieldCheck className="w-3.5 h-3.5 text-slate-400" />
        <span>End-to-end encrypted session with tenant isolation</span>
      </div>
    </div>
  );
};
