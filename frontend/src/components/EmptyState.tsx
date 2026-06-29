import { Library } from 'lucide-react';
import styles from './EmptyState.module.css';

interface EmptyStateProps {
  message: string;
}

export function EmptyState({ message }: EmptyStateProps) {
  return (
    <div className={styles.wrap}>
      <Library size={40} className={styles.icon} />
      <p className={styles.msg}>{message}</p>
    </div>
  );
}
