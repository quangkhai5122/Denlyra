import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Denlyra — React Foundation Prototype",
  description: "Synthetic-data-only dental practice demo, not medical software",
};

export default function RootLayout({ children }: Readonly<{children: React.ReactNode}>) {
  return <html lang="vi"><body>{children}</body></html>;
}
