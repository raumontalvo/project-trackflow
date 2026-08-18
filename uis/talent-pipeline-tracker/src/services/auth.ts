import { apiFetch } from './api';

export const TOKEN_KEY = 'trackflow_token';

export type AuthUser = {
  id: number;
  name?: string;
  email: string;
  is_active?: boolean;
};

export function getToken() {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string) {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
}

export async function login(email: string, password: string) {
  const body = new URLSearchParams();
  body.set('username', email);
  body.set('password', password);

  const response = await apiFetch<{ access_token: string; token_type: string }>('/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body,
  });

  setToken(response.access_token);
  return response;
}

export async function register(email: string, password: string) {
  return apiFetch<AuthUser>(
    `/auth/register?email=${encodeURIComponent(email)}&password=${encodeURIComponent(password)}`,
    { method: 'POST' }
  );
}

export async function getCurrentUser() {
  return apiFetch<AuthUser>('/auth/me');
}

export async function updateProfile(userId: number, data: { name: string; email: string }) {
  return apiFetch<AuthUser>(`/users/${userId}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

export async function changePassword(userId: number, password: string) {
  return apiFetch<AuthUser>(`/users/${userId}`, {
    method: 'PATCH',
    body: JSON.stringify({ password }),
  });
}

export async function forgotPassword(email: string) {
  return apiFetch<{ message: string }>('/auth/forgot-password', {
    method: 'POST',
    body: JSON.stringify({ email }),
  });
}

export async function resetPassword(token: string, newPassword: string) {
  return apiFetch<{ message: string }>('/auth/reset-password', {
    method: 'POST',
    body: JSON.stringify({
      token,
      new_password: newPassword,
    }),
  });
}

export function logout() {
  clearToken();
  window.location.href = '/login';
}