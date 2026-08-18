"use client";

import { useEffect } from "react";

export default function InventoryLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  useEffect(() => {
    const token = localStorage.getItem("access_token");

    if (!token) {
      window.location.replace("/login");
    }
  }, []);

  return children;
}