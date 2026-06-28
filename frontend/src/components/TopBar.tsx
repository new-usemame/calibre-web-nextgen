import { useState } from 'react';
import { BookMarked, LogOut, Menu, Search } from 'lucide-react';
import { Link, useLocation } from 'wouter';
import { Button } from './Button';
import { useT } from '../lib/i18n';
import styles from './TopBar.module.css';

interface TopBarProps {
  userName: string;
  onLogout: () => void;
  onMenu?: () => void;
}

export function TopBar({ userName, onLogout, onMenu }: TopBarProps) {
  const t = useT();
  const [, setLocation] = useLocation();
  const [q, setQ] = useState('');
  const onSearch = (e: React.FormEvent) => {
    e.preventDefault();
    const term = q.trim();
    setLocation(term ? `/?q=${encodeURIComponent(term)}` : '/');
  };
  return (
    <header className={styles.bar}>
      <div className={styles.left}>
        {onMenu && (
          <button className={styles.menuBtn} onClick={onMenu} aria-label={t('Open navigation')}>
            <Menu size={20} />
          </button>
        )}
        <Link href="/" className={styles.brand}>
          <BookMarked size={22} className={styles.brandIcon} />
          <span className={styles.brandText}>
            <span className={styles.brandMain}>Calibre-Web </span>
            <span className={styles.brandAccent}>NextGen</span>
          </span>
        </Link>
      </div>
      <form className={styles.search} onSubmit={onSearch} role="search">
        <Search size={16} className={styles.searchIcon} />
        <input
          type="search"
          className={styles.searchInput}
          placeholder={t('Search title, author…')}
          value={q}
          onChange={(e) => setQ(e.target.value)}
          aria-label={t('Search the library')}
        />
      </form>
      <div className={styles.right}>
        <Link href="/account" className={styles.userName} title={t('Account & settings')}>
          {userName}
        </Link>
        <Button variant="ghost" size="sm" onClick={onLogout}>
          <LogOut size={16} />
          {t('Sign out')}
        </Button>
      </div>
    </header>
  );
}
