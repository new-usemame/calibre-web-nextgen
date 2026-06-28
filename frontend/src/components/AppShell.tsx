import { useState, type ReactNode } from 'react';
import { TopBar } from './TopBar';
import { Sidebar } from './Sidebar';
import { HelpBanner } from './HelpBanner';
import styles from './AppShell.module.css';

interface AppShellProps {
  userName: string;
  onLogout: () => void;
  children: ReactNode;
}

export function AppShell({ userName, onLogout, children }: AppShellProps) {
  const [drawerOpen, setDrawerOpen] = useState(false);

  return (
    <div className={styles.shell}>
      <TopBar userName={userName} onLogout={onLogout} onMenu={() => setDrawerOpen(true)} />
      <HelpBanner />
      <div className={styles.body}>
        <Sidebar open={drawerOpen} onNavigate={() => setDrawerOpen(false)} />
        <div className={styles.content}>{children}</div>
      </div>
    </div>
  );
}
