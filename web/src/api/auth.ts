import api from './client';
import type { User } from '../types';

export const authApi = {
  login: (username: string, password: string) =>
    api.post<{ token: string; user: User }>('/auth/login', { username, password }),

  register: (data: { username: string; password: string; email?: string; invite_code: string }) =>
    api.post<{ token: string; user: User }>('/auth/register', data),

  me: () => api.get<{ user: User }>('/auth/me'),
};
