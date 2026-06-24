import { Link, useParams } from 'wouter';
import { Download } from 'lucide-react';
import { useBook, useToggleRead } from '../lib/queries';
import { Pill } from '../components/Pill';
import { SpinnerCentered } from '../components/Spinner';
import { EmptyState } from '../components/EmptyState';
import type { BookFormat } from '../lib/api';
import styles from './BookDetail.module.css';

function formatBytes(bytes: number): string {
  const mb = bytes / (1024 * 1024);
  return mb >= 0.1 ? `${mb.toFixed(1)} MB` : `${(bytes / 1024).toFixed(0)} KB`;
}

function formatPubdate(pubdate: string): string {
  // Try to parse as ISO date — return just the year if it looks like a date
  const d = new Date(pubdate);
  if (!isNaN(d.getTime())) {
    // If the time portion is midnight UTC it's likely just a year+date, show full date
    const year = d.getFullYear();
    const month = d.getMonth();
    const day = d.getDate();
    if (month === 0 && day === 1) return String(year);
    return d.toLocaleDateString(undefined, { year: 'numeric', month: 'long', day: 'numeric' });
  }
  return pubdate;
}

function readableFormat(fmt: BookFormat): string | null {
  const f = fmt.format.toLowerCase();
  if (f === 'epub' || f === 'pdf') return f;
  return null;
}

export function BookDetail() {
  const params = useParams<{ id: string }>();
  const id = params.id;

  const { data: book, isLoading, error } = useBook(id);
  const toggleRead = useToggleRead(id);

  if (isLoading) return <SpinnerCentered size={40} />;
  if (error || !book) {
    return (
      <main className={styles.container}>
        <Link href="/" className={styles.back}>← Library</Link>
        <EmptyState message={error instanceof Error ? error.message : 'Book not found.'} />
      </main>
    );
  }

  const readableFormats = book.formats.filter((f) => readableFormat(f) !== null);
  const primaryReadable = readableFormats[0] ?? null;

  const authorStr = book.authors.join(', ');

  return (
    <main className={styles.container}>
      <Link href="/" className={styles.back}>← Library</Link>

      <div className={styles.layout}>
        {/* LEFT: cover */}
        <div className={styles.coverCol}>
          {book.cover_url ? (
            <img
              src={book.cover_url}
              alt={book.title}
              className={styles.cover}
            />
          ) : (
            <div className={styles.coverFallback} aria-label={book.title}>
              <span className={styles.coverFallbackTitle}>{book.title}</span>
            </div>
          )}
        </div>

        {/* RIGHT: info */}
        <div className={styles.infoCol}>
          <div>
            <h1 className={styles.title}>{book.title}</h1>
            {authorStr && <p className={styles.authors}>{authorStr}</p>}
            {book.series && (
              <p className={styles.series}>
                {book.series} · Book {book.series_index}
              </p>
            )}
          </div>

          {/* Actions */}
          <div className={styles.actions}>
            {primaryReadable && (
              <a
                href={primaryReadable.read_url}
                className={styles.actionPrimary}
              >
                Read
              </a>
            )}

            <button
              className={book.read ? styles.readToggleActive : styles.readToggleGhost}
              onClick={() => toggleRead.mutate(!book.read)}
              disabled={toggleRead.isPending}
              aria-label={book.read ? 'Mark as unread' : 'Mark as read'}
            >
              {book.read ? 'Read ✓' : 'Mark as read'}
            </button>

            {book.formats.map((fmt) => (
              <a
                key={fmt.format}
                href={fmt.download_url}
                className={styles.downloadBtn}
                download
              >
                <Download size={15} />
                {fmt.format} · {formatBytes(fmt.size_bytes)}
              </a>
            ))}
          </div>

          {/* Tags */}
          {book.tags.length > 0 && (
            <div className={styles.tags}>
              {book.tags.map((tag) => (
                <Pill key={tag}>{tag}</Pill>
              ))}
            </div>
          )}

          {/* Metadata definition list */}
          <dl className={styles.meta}>
            {book.pubdate && (
              <>
                <dt className={styles.metaLabel}>Published</dt>
                <dd className={styles.metaValue}>{formatPubdate(book.pubdate)}</dd>
              </>
            )}
            {book.languages.length > 0 && (
              <>
                <dt className={styles.metaLabel}>{book.languages.length === 1 ? 'Language' : 'Languages'}</dt>
                <dd className={styles.metaValue}>{book.languages.join(', ')}</dd>
              </>
            )}
            {book.publishers.length > 0 && (
              <>
                <dt className={styles.metaLabel}>{book.publishers.length === 1 ? 'Publisher' : 'Publishers'}</dt>
                <dd className={styles.metaValue}>{book.publishers.join(', ')}</dd>
              </>
            )}
            {book.identifiers.map((id) => (
              <>
                <dt key={`dt-${id.type}`} className={styles.metaLabel}>{id.type.toUpperCase()}</dt>
                <dd key={`dd-${id.type}`} className={styles.metaValue}>{id.val}</dd>
              </>
            ))}
          </dl>

          {/* Description */}
          {book.description_html && (
            <div
              className={styles.description}
              // description_html is sanitized server-side in serialize_book_detail
              // (cps/clean_html.clean_string — bleach/nh3 allowlist, same as the
              // legacy templates), so it is safe to render here.
              // eslint-disable-next-line react/no-danger
              dangerouslySetInnerHTML={{ __html: book.description_html }}
            />
          )}
        </div>
      </div>
    </main>
  );
}
