import {
  AuthResponse,
  User,
  AnalysisSession,
  MediaAsset,
  AnalysisJob,
  AnalysisChunk,
  AnalysisResult,
  AnalysisConfig,
} from '../types/api';

const API_BASE = '/api/v1';

class ApiClient {
  private getAuthHeader(): Record<string, string> {
    const token = localStorage.getItem('token');
    return token ? { Authorization: `Bearer ${token}` } : {};
  }

  private async request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const url = `${API_BASE}${endpoint}`;
    const headers = {
      ...this.getAuthHeader(),
      ...((options.headers as Record<string, string>) || {}),
    };

    const response = await fetch(url, { ...options, headers });
    if (!response.ok) {
      if (response.status === 401) {
        localStorage.removeItem('token');
      }
      let errDetail = 'Request failed';
      try {
        const errorJson = await response.json();
        errDetail = errorJson.detail || errDetail;
      } catch {
        // Fallback to text
        errDetail = await response.text();
      }
      throw new Error(errDetail);
    }

    if (response.status === 204) {
      return null as unknown as T;
    }

    return response.json();
  }

  // --- Auth ---
  async login(email: string, password: string): Promise<AuthResponse> {
    const res = await this.request<AuthResponse>('/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });
    localStorage.setItem('token', res.access_token);
    return res;
  }

  async register(email: string, password: string): Promise<User> {
    return this.request<User>('/auth/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });
  }

  async getProfile(): Promise<User> {
    return this.request<User>('/auth/me');
  }

  logout(): void {
    localStorage.removeItem('token');
  }

  // --- Sessions ---
  async listSessions(): Promise<AnalysisSession[]> {
    return this.request<AnalysisSession[]>('/sessions');
  }

  async createSession(title: string, description?: string): Promise<AnalysisSession> {
    return this.request<AnalysisSession>('/sessions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title, description }),
    });
  }

  async getSession(id: string): Promise<AnalysisSession> {
    return this.request<AnalysisSession>(`/sessions/${id}`);
  }

  async deleteSession(id: string): Promise<void> {
    return this.request<void>(`/sessions/${id}`, { method: 'DELETE' });
  }

  // --- Media ---
  async uploadMedia(sessionId: string, file: File): Promise<MediaAsset> {
    const formData = new FormData();
    formData.append('file', file);
    return this.request<MediaAsset>(`/sessions/${sessionId}/media`, {
      method: 'POST',
      body: formData,
    });
  }

  async listMedia(sessionId: string): Promise<MediaAsset[]> {
    return this.request<MediaAsset[]>(`/sessions/${sessionId}/media`);
  }

  getMediaFileUrl(mediaId: string): string {
    return `${API_BASE}/sessions/media/${mediaId}/file`;
  }

  async getMediaBlobUrl(mediaId: string): Promise<string> {
    const token = localStorage.getItem('token');
    const res = await fetch(`${API_BASE}/sessions/media/${mediaId}/file`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!res.ok) {
      throw new Error(`Failed to load media (${res.status})`);
    }
    const blob = await res.blob();
    return URL.createObjectURL(blob);
  }

  // --- Analysis & Jobs ---
  async startAnalysis(sessionId: string, config: AnalysisConfig): Promise<AnalysisJob> {
    return this.request<AnalysisJob>(`/sessions/${sessionId}/analyze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(config),
    });
  }

  async getJob(jobId: string): Promise<AnalysisJob> {
    return this.request<AnalysisJob>(`/jobs/${jobId}`);
  }

  async getJobChunks(jobId: string): Promise<AnalysisChunk[]> {
    return this.request<AnalysisChunk[]>(`/jobs/${jobId}/chunks`);
  }

  async cancelJob(jobId: string): Promise<AnalysisJob> {
    return this.request<AnalysisJob>(`/jobs/${jobId}/cancel`, {
      method: 'POST',
    });
  }

  async getResults(sessionId: string): Promise<AnalysisResult | null> {
    return this.request<AnalysisResult | null>(`/sessions/${sessionId}/results`);
  }

  getExportUrl(sessionId: string, format: 'json' | 'csv'): string {
    return `${API_BASE}/sessions/${sessionId}/results/export?format=${format}`;
  }

  async downloadExport(sessionId: string, format: 'json' | 'csv'): Promise<void> {
    const token = localStorage.getItem('token');
    const res = await fetch(this.getExportUrl(sessionId, format), {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!res.ok) {
      throw new Error(`Export failed (${res.status})`);
    }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `crowd_analysis_${sessionId}.${format}`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  }
}

export const api = new ApiClient();
