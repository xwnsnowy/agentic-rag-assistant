"use client";

import { useEffect } from "react";
import { API_URL } from "@/lib/api";

// Fires once per page load from the root layout, so the wake-up starts while
// the visitor is still reading the landing page — not when they finally open
// /chat. /db/health (not /health) because it runs SELECT 1: that wakes both the
// Render free-tier dyno and Neon's auto-suspended compute in one request.
export function WarmUp() {
  useEffect(() => {
    fetch(`${API_URL}/db/health`, { cache: "no-store" }).catch(() => {});
  }, []);
  return null;
}
