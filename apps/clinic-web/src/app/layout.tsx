import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Denlyra — Không gian làm việc Phòng khám theo Vai trò (Synthetic Demo)",
  description: "Synthetic-data-only Vietnamese dental practice & EMR research demonstrator; NOT certified medical software",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="vi">
      <body>{children}</body>
    </html>
  );
}
