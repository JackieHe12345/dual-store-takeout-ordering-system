import type { Session } from './types';

const entries: Record<string, { kind: string; store: 'A' | 'B' | null }> = {
  Adiandiancan: { kind: 'customer', store: 'A' },
  Bdiandiancan: { kind: 'customer', store: 'B' },
  Adianneibuguanli: { kind: 'staff', store: 'A' },
  Bdianneibuguanli: { kind: 'staff', store: 'B' },
  neibuguanli: { kind: 'admin', store: null },
};
export const entryName = window.location.pathname.split('/')[1] || '';
export const entry = entries[entryName];
if (!entry) throw new Error('请从指定的门店网址访问');
export const basePath = `/${entryName}/`;
const sessionKey = `takeaway-session:${entryName}`;
export function readSession(): Session | null {
  try { return JSON.parse(sessionStorage.getItem(sessionKey) || 'null'); } catch { return null; }
}
export function saveSession(value: Session | null) {
  if (value) sessionStorage.setItem(sessionKey, JSON.stringify(value));
  else sessionStorage.removeItem(sessionKey);
}
export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}
export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  if (options.body && !(options.body instanceof FormData)) headers.set('Content-Type', 'application/json');
  const token = readSession()?.access_token;
  if (token) headers.set('Authorization', `Bearer ${token}`);
  let response: Response;
  try { response = await fetch(`${basePath}api/${path}`, { ...options, headers, credentials: 'omit' }); }
  catch { throw new ApiError(0, '网络连接失败，请稍后重试'); }
  if (!response.ok) {
    let message = `请求失败（${response.status}）`;
    try {
      const body = await response.json();
      if (typeof body.detail === 'string') message = body.detail;
      else if (Array.isArray(body.detail)) message = '请检查填写内容是否完整、格式是否正确';
    } catch { /* Keep status for proxy failures. */ }
    if (response.status === 401 && path !== 'auth/login' && token === readSession()?.access_token) {
      saveSession(null); window.dispatchEvent(new Event('session-expired'));
    }
    throw new ApiError(response.status, message);
  }
  return response.json();
}
export const money = (cents: number) => (cents / 100).toFixed(2).replace(/\.00$/, '').replace(/(\.\d)0$/, '$1');
export function imageUrl(value: string | null): string {
  if (!value) return '/media/placeholder.svg';
  try { const u = new URL(value, window.location.origin); return ['http:', 'https:'].includes(u.protocol) ? u.href : '/media/placeholder.svg'; }
  catch { return '/media/placeholder.svg'; }
}
export function imageFallback(event: Event) {
  const el = event.target as HTMLImageElement;
  if (!el.src.endsWith('/media/placeholder.svg')) el.src = '/media/placeholder.svg';
}

export function roleLabel(code: string): string {
  return ({ SUPER_ADMIN: '总管理员', STORE_ADMIN: '门店管理员', ORDER_OPERATOR: '订单操作员', KITCHEN_OPERATOR: '后厨操作员', DELIVERY_OPERATOR: '配送操作员' } as Record<string, string>)[code] || '后台账号';
}
