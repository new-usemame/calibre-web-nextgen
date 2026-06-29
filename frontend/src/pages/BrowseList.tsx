import { useMemo, useState } from 'react';
import { Link } from 'wouter';
import { Search } from 'lucide-react';
import { useEntityList } from '../lib/queries';
import { SpinnerCentered } from '../components/Spinner';
import { EmptyState } from '../components/EmptyState';
import { useT } from '../lib/i18n';
import styles from './BrowseList.module.css';

interface BrowseListProps {
  /** Endpoint/route segment, e.g. "authors". */
  plural: string;
  /** Heading, e.g. "Authors". */
  title: string;
}

export function BrowseList({ plural, title }: BrowseListProps) {
  const t = useT();
  const { data, isLoading, error } = useEntityList(plural);
  const [q, setQ] = useState('');

  const items = useMemo(() => {
    const all = data?.items ?? [];
    if (!q.trim()) return all;
    const needle = q.trim().toLowerCase();
    return all.filter((e) => e.name.toLowerCase().includes(needle));
  }, [data, q]);

  return (
    <main className={styles.container}>
      <div className={styles.header}>
        <h1 className={styles.title}>{title}</h1>
        {data && <span className={styles.count}>{data.items.length}</span>}
      </div>

      {data && data.items.length > 8 && (
        <div className={styles.searchWrap}>
          <Search size={15} className={styles.searchIcon} />
          <input
            type="search"
            className={styles.searchInput}
            placeholder={`Filter ${title.toLowerCase()}…`}
            value={q}
            onChange={(e) => setQ(e.target.value)}
            aria-label={`Filter ${title.toLowerCase()}`}
          />
        </div>
      )}

      {isLoading ? (
        <SpinnerCentered size={36} />
      ) : error ? (
        <EmptyState message={error instanceof Error ? error.message : t('Failed to load.')} />
      ) : items.length === 0 ? (
        <EmptyState message={q ? `No ${title.toLowerCase()} match "${q}".` : `No ${title.toLowerCase()} yet.`} />
      ) : (
        <ul className={styles.grid}>
          {items.map((e) => (
            <li key={String(e.id)}>
              <Link href={`/${plural}/${encodeURIComponent(String(e.id))}`} className={styles.item}>
                <span className={styles.name}>{e.name}</span>
                <span className={styles.badge}>{e.count}</span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
