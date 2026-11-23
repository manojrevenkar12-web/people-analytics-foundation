import type { Transition } from "framer-motion";

/** One easing for the console: quick out, settled in. */
export const settle: Transition = { type: "tween", ease: [0.2, 0.7, 0.2, 1], duration: 0.3 };

/** Bars and lines grow in once, on load. */
export const STAGGER = 0.06;
