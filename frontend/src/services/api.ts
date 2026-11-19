import {
  AnalysisSession,
  MediaAsset,
  AnalysisJob,
  AnalysisRun,
  AnalysisChunk,
  AnalysisResult,
  AnalysisConfig,
} from '../types/api';

const API_BASE = '/api/v1';

class ApiClient {
  private async request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const url = `${API_BASE}${endpoint}`;
    const headers = {
      ...((options.headers as Record<string, string>) || {}),
    };

    const response = await fetch(url, { ...options, headers });
    if (!response.ok) {
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
    const res = await fetch(`${API_BASE}/sessions/media/${mediaId}/file`);
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

  async listSessionJobs(sessionId: string): Promise<AnalysisRun[]> {
    return this.request<AnalysisRun[]>(`/sessions/${sessionId}/jobs`);
  }

  async getJobResults(jobId: string): Promise<AnalysisResult | null> {
    return this.request<AnalysisResult | null>(`/jobs/${jobId}/results`);
  }

  async getJob(jobId: string): Promise<AnalysisJob> {
    return this.request<AnalysisJob>(`/jobs/${jobId}`);
  }

  async getJobChunks(jobId: string, afterIndex = -1): Promise<AnalysisChunk[]> {
    return this.request<AnalysisChunk[]>(`/jobs/${jobId}/chunks?after_index=${afterIndex}`);
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

  async downloadTimeline(jobId: string, format: 'json' | 'csv'): Promise<void> {
    const response = await fetch(`${API_BASE}/jobs/${jobId}/analytics/export?format=${format}`);
    if (!response.ok) throw new Error('Timeline export failed');
    const url = URL.createObjectURL(await response.blob());
    const link = document.createElement('a'); link.href = url; link.download = `timeline_${jobId}.${format}`;
    document.body.appendChild(link); link.click(); link.remove(); URL.revokeObjectURL(url);
  }

  async downloadExport(sessionId: string, format: 'json' | 'csv'): Promise<void> {
    const res = await fetch(this.getExportUrl(sessionId, format));
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
