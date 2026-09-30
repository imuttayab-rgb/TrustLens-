import {
  BatteryFull,
  Box,
  Building2,
  Calendar,
  Gauge,
  HardDrive,
  Palette,
  Ruler,
  ShieldCheck,
  Tag,
  type LucideIcon,
} from 'lucide-react';

/** Best-effort icon per attribute key, purely decorative - the key/value
 * text itself is the real, seller-entered data either way. Unrecognised
 * keys (a listing's attributes are free-form per category) fall back to a
 * generic tag icon rather than guessing wrong. */
const ICON_BY_KEY: Record<string, LucideIcon> = {
  storage: HardDrive,
  color: Palette,
  colour: Palette,
  'pta status': ShieldCheck,
  'battery health': BatteryFull,
  included: Box,
  brand: Building2,
  make: Building2,
  model: Building2,
  year: Calendar,
  mileage: Gauge,
  size: Ruler,
};

export function attributeIcon(key: string): LucideIcon {
  return ICON_BY_KEY[key.trim().toLowerCase()] ?? Tag;
}
