"use client";
import { useEffect } from "react";

/** Counts one view per page load. Honors Do Not Track; sends only the item number. */
export function ViewBeacon({ docId }: { docId: number }) {
  useEffect(() => {
    const dnt = navigator.doNotTrack === "1" || (window as unknown as { doNotTrack?: string }).doNotTrack === "1";
    if (dnt) return;
    const body = new Blob([JSON.stringify({ document_id: docId })], { type: "application/json" });
    if (!navigator.sendBeacon?.("/api/views", body)) {
      fetch("/api/views", { method: "POST", body, keepalive: true }).catch(() => undefined);
    }
  }, [docId]);
  return null;
}
