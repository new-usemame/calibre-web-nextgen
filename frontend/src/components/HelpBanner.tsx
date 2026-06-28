import { useState } from 'react';
import { LifeBuoy, ArrowUpRight, X } from 'lucide-react';
import { useT } from '../lib/i18n';
import styles from './HelpBanner.module.css';

const DISMISS_KEY = 'cwng_help_banner_dismissed_v1';

/** A one-time, dismissible nudge shown in the new UI pointing users at the new
 *  Help menu (top-right) for reporting issues. Deliberately a cool teal tone —
 *  distinct from the app's warm amber accent and from the amber update banner —
 *  so it reads as a separate, friendly heads-up. Dismissal persists. */
export function HelpBanner() {
  const t = useT();
  const [show, setShow] = useState(() => {
    try { return localStorage.getItem(DISMISS_KEY) !== '1'; } catch { return true; }
  });
  if (!show) return null;

  const dismiss = () => {
    try { localStorage.setItem(DISMISS_KEY, '1'); } catch { /* private mode */ }
    setShow(false);
  };

  return (
    <div className={styles.banner} role="status">
      <span className={styles.iconWrap}><LifeBuoy size={17} /></span>
      <span className={styles.text}>
        {t('Need to report an issue? Try the new')} <strong>{t('Help menu')}</strong>
        <ArrowUpRight size={15} className={styles.arrow} aria-hidden="true" />
      </span>
      <button type="button" className={styles.close} onClick={dismiss} aria-label={t('Dismiss')}>
        <X size={16} />
      </button>
    </div>
  );
}
