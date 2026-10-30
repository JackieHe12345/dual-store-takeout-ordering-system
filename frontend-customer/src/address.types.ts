export interface Place {
  id: string;
  title: string;
  address: string;
  latitude: number;
  longitude: number;
  coordinate_system: 'WGS_84' | 'GCJ_02' | 'BD_09';
  accuracy_meters?: number;
  city: string | null;
}
export interface SavedAddress {
  id: string;
  contact: string;
  phone: string;
  detail: string;
  tag: string;
  isDefault: boolean;
  place: Place;
}
export interface DeliveryConfig {
  city: string | null;
  radius_meters: number;
  provider_ready?: boolean;
  places: Place[];
  location_confirmed: boolean;
  fees_configured: boolean;
  distance_method: 'straight';
}
export interface DeliveryCheck {
  available: boolean;
  reason: string | null;
  distance_meters: number | null;
  within_range: boolean | null;
  radius_meters: number;
  delivery_fee_cents: number | null;
  distance_method: 'straight';
}
