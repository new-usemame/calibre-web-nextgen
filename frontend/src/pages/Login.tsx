import React, { useState } from 'react';
import { BookMarked, KeyRound } from 'lucide-react';
import { Button } from '../components/Button';
import { Spinner } from '../components/Spinner';
import { useLogin, useAuthConfig, useRegister, useForgotPassword } from '../lib/queries';
import { ApiError } from '../lib/api';
import { useT } from '../lib/i18n';
import styles from './Login.module.css';

type Mode = 'login' | 'register' | 'forgot';

export function Login() {
  const t = useT();
  const [mode, setMode] = useState<Mode>('login');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [email, setEmail] = useState('');
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [okMsg, setOkMsg] = useState<string | null>(null);

  const login = useLogin();
  const register = useRegister();
  const forgot = useForgotPassword();
  const { data: cfg } = useAuthConfig();

  const reset = () => { setErrorMsg(null); setOkMsg(null); };

  const handleLogin = (e: React.FormEvent) => {
    e.preventDefault();
    reset();
    login.mutate({ username, password }, {
      onError: (err) =>
        setErrorMsg(err instanceof ApiError && err.status === 401
          ? 'Invalid username or password.' : 'Sign in failed. Please try again.'),
    });
  };

  const handleRegister = (e: React.FormEvent) => {
    e.preventDefault();
    reset();
    register.mutate({ name: username, email }, {
      onSuccess: (r) => { setOkMsg(r.message); setMode('login'); },
      onError: (err) => setErrorMsg(err instanceof ApiError ? err.message : 'Registration failed.'),
    });
  };

  const handleForgot = (e: React.FormEvent) => {
    e.preventDefault();
    reset();
    forgot.mutate(username, {
      onSuccess: (r) => { setOkMsg(r.message); setMode('login'); },
      onError: (err) => setErrorMsg(err instanceof ApiError ? err.message : 'Request failed.'),
    });
  };

  const standardDisabled = !!cfg?.standard_login_disabled;
  const canRegister = !!cfg?.public_registration && !!cfg?.mail_configured;
  const canForgot = !!cfg?.mail_configured;
  const providers = cfg?.oauth_providers ?? [];

  return (
    <div className={styles.page}>
      <div className={styles.card}>
        <div className={styles.brandMark}>
          <BookMarked size={32} className={styles.brandIcon} />
          <span className={styles.brandText}>Calibre-Web <span className={styles.brandAccent}>NextGen</span></span>
        </div>
        <p className={styles.tagline}>
          {mode === 'register' ? t('Create your account')
            : mode === 'forgot' ? t('Reset your password')
              : t('Your personal digital library')}
        </p>

        {okMsg && <div className={styles.ok} role="status">{okMsg}</div>}

        {/* LOGIN */}
        {mode === 'login' && !standardDisabled && (
          <form className={styles.form} onSubmit={handleLogin} noValidate>
            <label className={styles.field}>
              <span className={styles.label}>{t('Username')}</span>
              <input type="text" className={styles.input} value={username}
                onChange={(e) => setUsername(e.target.value)} autoComplete="username" autoFocus required />
            </label>
            <label className={styles.field}>
              <span className={styles.label}>{t('Password')}</span>
              <input type="password" className={styles.input} value={password}
                onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" required />
            </label>
            {errorMsg && <div className={styles.error} role="alert">{errorMsg}</div>}
            <Button type="submit" variant="primary" className={styles.submitBtn} disabled={login.isPending}>
              {login.isPending ? (<><Spinner size={16} /> {t('Signing in…')}</>) : t('Sign in')}
            </Button>
          </form>
        )}

        {/* REGISTER */}
        {mode === 'register' && (
          <form className={styles.form} onSubmit={handleRegister} noValidate>
            {!cfg?.register_email && (
              <label className={styles.field}>
                <span className={styles.label}>{t('Username')}</span>
                <input type="text" className={styles.input} value={username}
                  onChange={(e) => setUsername(e.target.value)} autoComplete="username" autoFocus required />
              </label>
            )}
            <label className={styles.field}>
              <span className={styles.label}>{t('Email')}</span>
              <input type="email" className={styles.input} value={email}
                onChange={(e) => setEmail(e.target.value)} autoComplete="email"
                autoFocus={!!cfg?.register_email} required />
            </label>
            {errorMsg && <div className={styles.error} role="alert">{errorMsg}</div>}
            <Button type="submit" variant="primary" className={styles.submitBtn} disabled={register.isPending}>
              {register.isPending ? (<><Spinner size={16} /> {t('Registering…')}</>) : t('Create account')}
            </Button>
          </form>
        )}

        {/* FORGOT */}
        {mode === 'forgot' && (
          <form className={styles.form} onSubmit={handleForgot} noValidate>
            <label className={styles.field}>
              <span className={styles.label}>{t('Username')}</span>
              <input type="text" className={styles.input} value={username}
                onChange={(e) => setUsername(e.target.value)} autoComplete="username" autoFocus required />
            </label>
            {errorMsg && <div className={styles.error} role="alert">{errorMsg}</div>}
            <Button type="submit" variant="primary" className={styles.submitBtn} disabled={forgot.isPending}>
              {forgot.isPending ? (<><Spinner size={16} /> {t('Sending…')}</>) : t('Email me a reset')}
            </Button>
          </form>
        )}

        {/* OAuth providers */}
        {providers.length > 0 && mode === 'login' && (
          <div className={styles.oauth}>
            <div className={styles.divider}><span>{t('or continue with')}</span></div>
            {providers.map((p) => (
              <a key={p.id} href={p.url} className={styles.oauthBtn}>{p.name}</a>
            ))}
          </div>
        )}

        {/* Magic-link (remote) login — admin toggle config_remote_login */}
        {mode === 'login' && cfg?.remote_login && cfg.remote_login_url && (
          <a href={cfg.remote_login_url} className={styles.magicLink}>
            <KeyRound size={15} />
            {t('Log in with a magic link')}
          </a>
        )}

        {/* Mode switches */}
        <div className={styles.switches}>
          {mode !== 'login' && (
            <button type="button" className={styles.linkBtn} onClick={() => { setMode('login'); reset(); }}>
              {t('← Back to sign in')}
            </button>
          )}
          {mode === 'login' && canForgot && (
            <button type="button" className={styles.linkBtn} onClick={() => { setMode('forgot'); reset(); }}>
              {t('Forgot password?')}
            </button>
          )}
          {mode === 'login' && canRegister && (
            <button type="button" className={styles.linkBtn} onClick={() => { setMode('register'); reset(); }}>
              {t('Create an account')}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
