export interface Store { id: number; slug: string; name: string; phone: string; address: string; logo_url: string | null; enabled?: boolean; delivery_radius_meters?: number; latitude?: string; longitude?: string }
export interface Dish {
  id: number; category_id: number; name: string; slug: string; description: string | null;
  image_url: string | null; price_cents: number; original_price_cents: number | null;
  monthly_sales: number; stock: number | null; requires_options: boolean;
  sold_out: boolean; enabled: boolean; sort_order: number;
}
export interface Category { id: number; name: string; slug: string; description: string | null; icon: string | null; sort_order: number; enabled: boolean; dishes: Dish[] }
export interface Menu { store: Store; categories: Category[] }
export interface User { id: number; username: string; display_name: string; role_code: string; store_id: number | null; enabled: boolean; permissions: string[] }
export interface Session { access_token: string; user: User; expires_in: number }
