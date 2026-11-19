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

export interface AnalysisRun extends AnalysisJob {
  confidence_threshold: number;
  peak_count: number | null;
  result_available: boolean;
}

export interface FrameGroupAnnotation {
  group_id: number;
  cluster_id: number;
  member_count: number;
  centroid: [number, number];
  bounding_box: [number, number, number, number];
  convex_hull: [number, number][] | null;
  mean_nn_distance: number;
  density_per_kpx: number;
  motion_angle_deg: number | null;
  motion_speed: number | null;
  speed_unit?: string;
  observation_status?: string;
  track_ids?: number[];
  motion_status?: string;
  direction_label: string;
  motion_confidence: number;
  formation_state: string;
}

export interface CrowdEvent {
  state: string;
  timestamp?: number;
  baseline_count?: number;
  current_count?: number;
  absolute_increase?: number;
  percentage_increase?: number | null;
  reason?: string;
}

export interface FrameAnnotation {
  annotation_version?: number;
  valid_until?: number;
  crowd_event?: CrowdEvent;
  camera_status?: string;
  tracked_count?: number;
  cluster_count?: number;
  mean_closeness_px?: number;
  mean_density_per_kpx?: number;
  detector?: string;
  detection_diagnostics?: {requested_threshold?: number; max_detection_score?: number; candidates_at_recommended_threshold?: number | null};
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
  media_asset_id?: string;
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
  detector_backend?: 'auto' | 'person' | 'blob';
  clustering_method?: 'hac' | 'density';
  confidence_threshold: number;
  distance_threshold: number;
  linkage_method: 'ward' | 'complete' | 'average';
  sample_interval_frames?: number;
  camera_mode?: 'auto' | 'static';
  motion_min_displacement_px?: number;
  motion_smoothing?: number;
  chunk_duration_sec?: number;
  crowd_increase?: {
    enabled?: boolean;
    window_seconds?: number;
    min_history_seconds?: number;
    min_samples?: number;
    min_absolute?: number;
    min_percent?: number;
    persistence_seconds?: number;
    cooldown_seconds?: number;
  };
}
