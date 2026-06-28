import { useCallback, useState } from 'react';

/** A boolean state mirrored to localStorage under `key`. Survives reloads and is
 *  shared by any component reading the same key (e.g. a section's close button and
 *  a settings toggle). Falls back gracefully if storage is unavailable. */
export function usePersistentBool(key: string, fallback: boolean) {
  const [val, setVal] = useState<boolean>(() => {
    try {
      const v = localStorage.getItem(key);
      return v === null ? fallback : v === '1';
    } catch {
      return fallback;
    }
  });
  const set = useCallback((next: boolean) => {
    setVal(next);
    try {
      localStorage.setItem(key, next ? '1' : '0');
    } catch {
      /* storage unavailable (private mode / quota) — keep in-memory only */
    }
  }, [key]);
  return [val, set] as const;
}
