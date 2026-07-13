import type { Metadata } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: "Living RAG | Policy Intelligence",
  description:
    "面向电商售后与会员服务的动态知识库事实保鲜与冲突治理 Agent。",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}