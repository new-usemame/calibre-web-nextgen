import { Check } from 'lucide-react';
import { Link } from 'wouter';
import type { Book } from '../lib/api';
import { BookCover } from './BookCover';
import styles from './BookCard.module.css';

interface BookCardProps {
  book: Book;
  style?: React.CSSProperties;
}

export function BookCard({ book, style }: BookCardProps) {
  const authorStr = book.authors.join(', ');

  return (
    <Link href={`/book/${book.id}`} className={styles.cardLink}>
      <article className={styles.card} style={style} tabIndex={0}>
        <div className={styles.coverWrap}>
          <BookCover coverUrl={book.cover_url} title={book.title} />
          {book.read && (
            <span className={styles.readBadge} aria-label="Read" title="Read">
              <Check size={14} strokeWidth={3} />
            </span>
          )}
        </div>
        <div className={styles.info}>
          <p className={styles.title}>{book.title}</p>
          <p className={styles.author}>{authorStr}</p>
        </div>
      </article>
    </Link>
  );
}
