"use client";

import { useEffect } from "react";

import { recordPerformance } from "@/lib/instrumentation";

/** Collects content-free browser performance baselines for in-page observers. */
export function PerformanceBaseline() {
  useEffect(() => {
    const navigation = performance.getEntriesByType("navigation")[0] as PerformanceNavigationTiming | undefined;
    if (navigation) {
      recordPerformance("TTFB", navigation.responseStart, "ms");
      recordPerformance("DOM_CONTENT_LOADED", navigation.domContentLoadedEventEnd, "ms");
      recordPerformance("LOAD", navigation.loadEventEnd, "ms");
    }

    const observers: PerformanceObserver[] = [];
    const observe = (type: string, callback: (entries: PerformanceEntry[]) => void) => {
      if (!PerformanceObserver.supportedEntryTypes?.includes(type)) return;
      const observer = new PerformanceObserver((list) => callback(list.getEntries()));
      observer.observe({ type, buffered: true });
      observers.push(observer);
    };
    observe("largest-contentful-paint", (entries) => {
      const last = entries.at(-1);
      if (last) recordPerformance("LCP", last.startTime, "ms");
    });
    observe("layout-shift", (entries) => {
      const cls = entries.reduce((total, entry) => {
        const shift = entry as PerformanceEntry & { value?: number; hadRecentInput?: boolean };
        return total + (shift.hadRecentInput ? 0 : shift.value ?? 0);
      }, 0);
      if (cls > 0) recordPerformance("CLS", cls, "score");
    });
    observe("event", (entries) => {
      const longest = entries.reduce((max, entry) => {
        const duration = (entry as PerformanceEntry & { duration?: number }).duration ?? 0;
        return Math.max(max, duration);
      }, 0);
      if (longest > 0) recordPerformance("EVENT_DURATION_MAX", longest, "ms");
    });

    return () => observers.forEach((observer) => observer.disconnect());
  }, []);

  return null;
}
