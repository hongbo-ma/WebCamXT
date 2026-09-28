import api from './client';
import type { User, InviteCode } from '../types';

export const adminApi = {
  createInvite: (expiresDays?: number) =>
    api.post<InviteCode>('/admin/invites', { expires_days: expiresDays }),

  listInvites: () => api.get<{ invites: InviteCode[] }>('/admin/invites'),

  revokeInvite: (id: number) => api.delete<{ success: boolean }>(`/admin/invites/${id}`),

  listUsers: () => api.get<{ users: User[] }>('/admin/users'),

  deleteUser: (id: number) => api.delete<{ success: boolean }>(`/admin/users/${id}`),

  updateUserRole: (id: number, role: 'admin' | 'user') =>
    api.patch<{ user: User }>(`/admin/users/${id}`, { role }),
};
