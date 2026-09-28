import api from './client';
import type { FileRecord, Combinations } from '../types';

export const filesApi = {
  list: () => api.get<{ files: FileRecord[] }>('/files'),

  upload: (file: File) => {
    const form = new FormData();
    form.append('file', file);
    return api.post<{ file_id: number; combinations: Combinations }>('/upload', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },

  get: (id: number) => api.get<FileRecord>(`/files/${id}`),

  delete: (id: number) => api.delete<{ success: boolean }>(`/files/${id}`),
};
