import styles from './Pill.module.css';

interface PillProps {
  children: React.ReactNode;
}

export function Pill({ children }: PillProps) {
  return <span className={styles.pill}>{children}</span>;
}
