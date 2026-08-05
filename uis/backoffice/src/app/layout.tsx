import type { Metadata } from "next";
import Link from "next/link";
import { Geist, Geist_Mono } from "next/font/google";
import styles from "./layout.module.css";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "TrackFlow Backoffice",
  description: "Internal logistics operations dashboard for TrackFlow.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable}`}
    >
      <body>
        <div className={styles.shell}>
          <header className={styles.topbar}>
            <div className={styles.brand}>
              <span className={styles.logo}>TF</span>

              <div className={styles.brandText}>
                <strong>TrackFlow Backoffice</strong>
                <span>Internal logistics operations</span>
              </div>
            </div>

            <span className={styles.environment}>Operations online</span>
          </header>

          <div className={styles.body}>
            <aside className={styles.sidebar}>
              <p className={styles.navLabel}>Workspace</p>

              <nav className={styles.nav} aria-label="Backoffice navigation">
                <Link href="/">Overview</Link>
                <a href="#inventory">Inventory</a>
                <a href="#carriers">Carriers</a>
                <a href="#shipments">Shipments</a>
              </nav>
            </aside>

            <div className={styles.content}>{children}</div>
          </div>
        </div>
      </body>
    </html>
  );
}
