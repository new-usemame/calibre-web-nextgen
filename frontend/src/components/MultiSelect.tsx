import { useState, useRef, useEffect, useMemo } from 'react';
import { X, ChevronDown } from 'lucide-react';
import { useT } from '../lib/i18n';
import styles from './MultiSelect.module.css';

export interface Option {
  id: string | number;
  name: string;
}

interface MultiSelectProps {
  options: Option[];
  /** Selected option ids. */
  value: (string | number)[];
  onChange: (next: (string | number)[]) => void;
  placeholder?: string;
}

/** Chip-based searchable multi-select. Reused by the advanced-search form for
 *  tags / series / languages / formats (include and exclude pickers). */
export function MultiSelect({ options, value, onChange, placeholder = 'Select…' }: MultiSelectProps) {
  const t = useT();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const wrapRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', onDoc);
    return () => document.removeEventListener('mousedown', onDoc);
  }, [open]);

  const byId = useMemo(() => new Map(options.map((o) => [String(o.id), o])), [options]);
  const selectedSet = useMemo(() => new Set(value.map(String)), [value]);

  const available = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return options
      .filter((o) => !selectedSet.has(String(o.id)))
      .filter((o) => !needle || o.name.toLowerCase().includes(needle))
      .slice(0, 50);
  }, [options, selectedSet, query]);

  const add = (id: string | number) => {
    onChange([...value, id]);
    setQuery('');
  };
  const remove = (id: string | number) => onChange(value.filter((v) => String(v) !== String(id)));

  return (
    <div className={styles.wrap} ref={wrapRef}>
      <div className={styles.control} onClick={() => setOpen(true)}>
        {value.length === 0 && !open && <span className={styles.placeholder}>{placeholder}</span>}
        {value.map((id) => (
          <span key={String(id)} className={styles.chip}>
            {byId.get(String(id))?.name ?? id}
            <button
              type="button"
              className={styles.chipX}
              aria-label={t('Remove')}
              onClick={(e) => {
                e.stopPropagation();
                remove(id);
              }}
            >
              <X size={12} />
            </button>
          </span>
        ))}
        {open && (
          <input
            className={styles.input}
            value={query}
            autoFocus
            placeholder={value.length === 0 ? placeholder : ''}
            onChange={(e) => setQuery(e.target.value)}
            aria-label={placeholder}
          />
        )}
        <ChevronDown size={15} className={styles.caret} />
      </div>

      {open && available.length > 0 && (
        <ul className={styles.menu} role="listbox">
          {available.map((o) => (
            <li key={String(o.id)}>
              <button type="button" className={styles.option} onClick={() => add(o.id)}>
                {o.name}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
