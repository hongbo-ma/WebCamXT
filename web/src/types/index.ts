export interface User {
  id: number;
  username: string;
  email?: string;
  role: 'admin' | 'user';
  created_at?: string;
  file_count?: number;
}

export interface Combinations {
  vgs_vds_map: Record<string, { vgs: number[]; vds: number[] }>;
  w_l_pairs: { w: number; l: number }[];
}

export interface FileRecord {
  id: number;
  original_filename: string;
  file_size: number;
  uploaded_at: string;
  combinations: Combinations | null;
}

export interface DataParams {
  t_tail: number;
  t_deep: number;
  g_tail: number;
  g_deep: number;
  T: number;
  mu_free: number;
  Vfb: number;
  phi_F0: number;
  CoxArea: number;
  M?: number;
  error_tolerance?: number;
  max_iterations?: number;
}

export interface SimRequest {
  file_id: number;
  w: number;
  l: number;
  type_sel: 0 | 1;
  vgs_min: number;
  vgs_max: number;
  vds_min: number;
  vds_max: number;
  step: number;
  enable_rc: boolean;
  max_iterations?: number;
  error_tolerance?: number;
  data_params: DataParams;
}

export interface FittingResults {
  U_FE_1: string[];
  U_FE_2: string[];
  SS: string[];
  V_th: string;
}

export interface SimResponse {
  x: number[];
  y: number[];
  enable_rc: boolean;
  rc_array: number[] | null;
  fitting_error_rate: number;
  w: number;
  l: number;
  type_sel: number;
  U_FE_1: string[];
  U_FE_2: string[];
  SS: string[];
  V_th: string;
}

export interface InviteCode {
  id: number;
  code: string;
  is_used: boolean;
  created_at: string;
  expires_at: string;
  used_at: string | null;
  used_by_username: string | null;
  is_active: boolean;
}

export interface Curve {
  id: string;
  name: string;
  source: 'exp' | 'sim';
  x: number[];
  y: number[];
  visible: boolean;
  color: string;
}
