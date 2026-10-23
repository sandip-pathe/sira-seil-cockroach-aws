import styles from "./skip-link.module.css";

/** Keyboard-only shortcut to the current page's primary content landmark. */
export function SkipLink({ href, children }: { href: `#${string}`; children: string }) {
  return <a className={styles.skipLink} href={href}>{children}</a>;
}
