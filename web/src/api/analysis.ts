import api from './client';
import type { DataParams, SimRequest, FittingResults, SimResponse } from '../types';

export const analysisApi = {
  plotData: (params: { file_id: number; w: number; l: number; type: string; v_value: number }) =>
    api.post<{ x: number[]; y: number[] }>('/plot-data', params),

  autoFitting: (params: { file_id: number; w: number; l: number; data_params: DataParams }) =>
    api.post<FittingResults>('/auto_fitting', params),

  simulation: (params: SimRequest) =>
    api.post<SimResponse>('/simulation', params),
};
