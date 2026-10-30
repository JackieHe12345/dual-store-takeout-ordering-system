import { api, entryName } from './api';
export type Data = Record<string, any>;
const key = `takeaway-member:${entryName}`;
let memoryToken = '';
export function memberToken() { try { return localStorage.getItem(key) || memoryToken; } catch { return memoryToken; } }
export function setMemberToken(value: string) { memoryToken = value; try { if (value) localStorage.setItem(key,value); else localStorage.removeItem(key); } catch { /* Keep this session usable. */ } }
export async function memberApi<T = Data>(path: string, method = 'GET', data?: unknown): Promise<T> {
  return api<T>(`commerce/${path}`, {method, headers: {'X-Member-Token': memberToken()}, ...(data === undefined ? {} : {body:JSON.stringify(data)})});
}
export const randomKey = () => Array.from(crypto.getRandomValues(new Uint8Array(16)), b => b.toString(16).padStart(2,'0')).join('');
export const stateLabel = (s:string) => ({PENDING:'待接单',ACCEPTED:'已接单',PREPARING:'制作中',READY:'待取餐 / 配送',DELIVERING:'配送中',COMPLETED:'已完成',CANCELLED:'已取消',REDEEMED:'已核销',AVAILABLE:'可使用',RESERVED:'订单占用',USED:'已使用'} as Record<string,string>)[s] || s;
export const modeLabel = (s:string) => ({pickup:'到店自提',dine_in:'店内就餐',delivery:'外送'} as Record<string,string>)[s] || s;
export const dateLabel = (s:string) => s ? new Date(s).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',hour12:false}) : '—';
