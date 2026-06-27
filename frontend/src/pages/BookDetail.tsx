import { useState } from 'react';
import { Link, useParams } from 'wouter';
import { Download, Pencil, Star, Archive, EyeOff, Eye, Send } from 'lucide-react';
import {
  useBook, useToggleRead, useToggleFavorite, useToggleArchived, useToggleHidden,
  useSendToEreader, useMe,
} from '../lib/queries';
import { Pill } from '../components/Pill';
import { AddToShelf } from '../components/AddToShelf';
import { SpinnerCentered } from '../components/Spinner';
import { EmptyState } from '../components/EmptyState';
import type { BookFormat } from '../lib/api';
import { ApiError } from '../lib/api';
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

interface SendPanelProps {
  formats: string[];
  pending: boolean;
  banner: { ok: boolean; text: string } | null;
  onSend: (format: string, convert: boolean, emails: string) => void;
}

/** Compact send-to-e-reader form: pick a format, optionally convert, optionally
 *  override the recipient(s). Empty recipient → user's configured e-reader email. */
function SendPanel({ formats, pending, banner, onSend }: SendPanelProps) {
  const [format, setFormat] = useState(formats[0] ?? '');
  const [convert, setConvert] = useState(false);
  const [emails, setEmails] = useState('');
  return (
    <div className={styles.sendPanel}>
      <div className={styles.sendRow}>
        <label className={styles.sendField}>
          <span>Format</span>
          <select value={format} onChange={(e) => setFormat(e.target.value)}>
            {formats.map((f) => <option key={f} value={f}>{f.toUpperCase()}</option>)}
          </select>
        </label>
        <label className={styles.sendField}>
          <span>Recipient(s) — blank = your e-reader email</span>
          <input
            type="text" value={emails} placeholder="a@kindle.com, b@kindle.com"
            onChange={(e) => setEmails(e.target.value)}
          />
        </label>
      </div>
      <div className={styles.sendActions}>
        <label className={styles.sendConvert}>
          <input type="checkbox" checked={convert} onChange={(e) => setConvert(e.target.checked)} />
          Convert before sending
        </label>
        <button
          className={styles.actionPrimary}
          disabled={pending || !format}
          onClick={() => onSend(format, convert, emails.trim())}
        >
          {pending ? 'Sending…' : 'Send'}
        </button>
      </div>
      {banner && <p className={banner.ok ? styles.sendOk : styles.sendErr}>{banner.text}</p>}
    </div>
  );
}

export function BookDetail() {
  const params = useParams<{ id: string }>();
  const id = params.id;

  const { data: book, isLoading, error } = useBook(id);
  const toggleRead = useToggleRead(id);
  const toggleFavorite = useToggleFavorite(id);
  const toggleArchived = useToggleArchived(id);
  const toggleHidden = useToggleHidden(id);
  const sendToEreader = useSendToEreader(id);
  const me = useMe().data;
  const [sendOpen, setSendOpen] = useState(false);
  const [sendBanner, setSendBanner] = useState<{ ok: boolean; text: string } | null>(null);

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
  const hasEpub = book.formats.some((f) => f.format.toLowerCase() === 'epub');

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
            {book.authors.length > 0 && (
              <p className={styles.authors}>
                {book.authors.map((a, i) => (
                  <span key={a.id}>
                    {i > 0 && ', '}
                    <Link href={`/authors/${a.id}`} className={styles.metaLink}>{a.name}</Link>
                  </span>
                ))}
              </p>
            )}
            {book.series && (
              <p className={styles.series}>
                <Link href={`/series/${book.series.id}`} className={styles.metaLink}>
                  {book.series.name}
                </Link>
                {' · Book '}
                {book.series_index}
              </p>
            )}
          </div>

          {/* Actions */}
          <div className={styles.actions}>
            {hasEpub ? (
              // EPUB opens in the in-browser SPA reader (resumes saved progress).
              <Link href={`/read/${book.id}`} className={styles.actionPrimary}>
                Read
              </Link>
            ) : primaryReadable ? (
              // Other readable formats (PDF, …) use the classic full-page reader.
              <a href={primaryReadable.read_url} className={styles.actionPrimary}>
                Read
              </a>
            ) : null}

            <button
              className={book.read ? styles.readToggleActive : styles.readToggleGhost}
              onClick={() => toggleRead.mutate(!book.read)}
              disabled={toggleRead.isPending}
              aria-label={book.read ? 'Mark as unread' : 'Mark as read'}
            >
              {book.read ? 'Read ✓' : 'Mark as read'}
            </button>

            <AddToShelf bookId={book.id} />

            {/* Star / favorite */}
            <button
              className={book.favorited ? styles.readToggleActive : styles.readToggleGhost}
              onClick={() => toggleFavorite.mutate()}
              disabled={toggleFavorite.isPending}
              aria-label={book.favorited ? 'Remove from favorites' : 'Add to favorites'}
            >
              <Star size={14} fill={book.favorited ? 'currentColor' : 'none'} />
              {book.favorited ? 'Favorited' : 'Favorite'}
            </button>

            {/* Archive (sync-pause) */}
            <button
              className={book.archived ? styles.readToggleActive : styles.readToggleGhost}
              onClick={() => toggleArchived.mutate()}
              disabled={toggleArchived.isPending}
              aria-label={book.archived ? 'Unarchive' : 'Archive'}
            >
              <Archive size={14} />
              {book.archived ? 'Archived' : 'Archive'}
            </button>

            {/* Hide / unhide — only shown when hiding is enabled, or to unhide an
                already-hidden book (so an admin disabling the flag can't strand it). */}
            {(me?.features?.hide_books || book.hidden) && (
              <button
                className={book.hidden ? styles.readToggleActive : styles.readToggleGhost}
                onClick={() => toggleHidden.mutate()}
                disabled={toggleHidden.isPending}
                aria-label={book.hidden ? 'Unhide' : 'Hide'}
              >
                {book.hidden ? <Eye size={14} /> : <EyeOff size={14} />}
                {book.hidden ? 'Unhide' : 'Hide'}
              </button>
            )}

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

            {/* Send to e-reader — gated on mail being configured + download role */}
            {me?.features?.mail_configured && me?.role?.download && book.formats.length > 0 && (
              <button
                className={styles.downloadBtn}
                onClick={() => { setSendOpen((v) => !v); setSendBanner(null); }}
                aria-label="Send to e-reader"
              >
                <Send size={14} />
                Send to e-reader
              </button>
            )}

            {me?.role?.edit && (
              <Link href={`/book/${book.id}/edit`} className={styles.downloadBtn}>
                <Pencil size={14} />
                Edit
              </Link>
            )}
          </div>

          {/* Send-to-e-reader panel */}
          {sendOpen && (
            <SendPanel
              formats={book.formats.map((f) => f.format)}
              pending={sendToEreader.isPending}
              banner={sendBanner}
              onSend={(format, convert, emails) => {
                setSendBanner(null);
                sendToEreader.mutate(
                  { format, convert, emails: emails || undefined },
                  {
                    onSuccess: (r) => { setSendBanner({ ok: true, text: r.message }); },
                    onError: (err) =>
                      setSendBanner({ ok: false, text: err instanceof ApiError ? err.message : 'Send failed.' }),
                  },
                );
              }}
            />
          )}

          {/* Tags */}
          {book.tags.length > 0 && (
            <div className={styles.tags}>
              {book.tags.map((tag) => (
                <Link key={tag.id} href={`/tags/${tag.id}`} className={styles.tagLink}>
                  <Pill>{tag.name}</Pill>
                </Link>
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
                <dd className={styles.metaValue}>
                  {book.languages.map((l, i) => (
                    <span key={l.id}>
                      {i > 0 && ', '}
                      <Link href={`/languages/${l.id}`} className={styles.metaLink}>{l.name}</Link>
                    </span>
                  ))}
                </dd>
              </>
            )}
            {book.publishers.length > 0 && (
              <>
                <dt className={styles.metaLabel}>{book.publishers.length === 1 ? 'Publisher' : 'Publishers'}</dt>
                <dd className={styles.metaValue}>
                  {book.publishers.map((p, i) => (
                    <span key={p.id}>
                      {i > 0 && ', '}
                      <Link href={`/publishers/${p.id}`} className={styles.metaLink}>{p.name}</Link>
                    </span>
                  ))}
                </dd>
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
