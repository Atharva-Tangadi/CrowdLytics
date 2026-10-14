export interface User {
  id: string;
  email: string;
  role: string;
  created_at: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user_id: string;
  email: string;
}

export interface AnalysisSession {
  id: string;
  user_id: string;
  title: string;
  description: string | null;
  created_at: string;
  updated_at: string;
}

export interface MediaAsset {
  id: string;
  session_id: string;
  media_type: 'IMAGE' | 'VIDEO';
  original_filename: string;
  file_size_bytes: number;
  mime_type: string;
  width: number | null;
  height: number | null;
  duration_seconds: number | null;
  fps: number | null;
  frame_count: number | null;
  created_at: string;
}

export interface AnalysisJob {
  id: string;
  session_id: string;
  media_asset_id: string;
  status: 'QUEUED' | 'RUNNING' | 'COMPLETED' | 'FAILED' | 'CANCELLED';
  progress_pct: number;
  current_stage: string;
  error_message: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

export interface FrameGroupAnnotation {
  group_id: number;
  cluster_id: number;
  member_count: number;
  centroid: [number, number];
  bounding_box: [number, number, number, number];
  convex_hull: [number, number][];
  mean_nn_distance: number;
  density_per_kpx: number;
  motion_angle_deg: number | null;
  motion_speed: number;
  direction_label: string;
  motion_confidence: number;
  formation_state: string;
}

export interface FrameAnnotation {
  timestamp: number;
  frame_index: number;
  crowd_count: number;
  confidence: number;
  groups: FrameGroupAnnotation[];
}

export interface AnalysisChunk {
  id: string;
  job_id: string;
  chunk_index: number;
  start_timestamp: number;
  end_timestamp: number;
  frame_count: number;
  status: string;
  frame_data_json: string;
  created_at: string;
}

export interface CrowdGroupSummary {
  id: string;
  cluster_id: number;
  member_count: number;
  centroid_x: number;
  centroid_y: number;
  bounding_box_json: string;
  convex_hull_area: number;
  mean_nn_distance: number;
  density_per_kpx: number;
  motion_angle_deg: number | null;
  motion_speed: number | null;
  formation_state: string | null;
}

export interface AnalysisResult {
  id: string;
  job_id: string;
  total_crowd_count: number;
  confidence_score: number;
  cluster_count: number;
  mean_closeness_px: number;
  mean_density_per_kpx: number;
  dominant_direction_deg: number | null;
  dominant_formation_type: string | null;
  summary_data_json: string | null;
  groups: CrowdGroupSummary[];
  created_at: string;
}

export interface AnalysisConfig {
  media_asset_id: string;
  confidence_threshold: number;
  distance_threshold: number;
  linkage_method: 'ward' | 'complete' | 'average';
  sample_interval_frames?: number;
}
