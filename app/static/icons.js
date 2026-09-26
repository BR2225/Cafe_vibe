// Small hand-drawn line-icon set used in place of emoji throughout the UI.
// Each function returns an inline <svg> string; pass extra classes via `cls`.
const Icon = (() => {
  const svg = (body, cls = "") =>
    `<svg class="icon ${cls}" viewBox="0 0 20 20" fill="none" aria-hidden="true">${body}</svg>`;

  return {
    work: (c) => svg(`<rect x="3" y="4" width="14" height="9" rx="1.5" stroke="currentColor" stroke-width="1.5"/><path d="M1.5 16.5h17" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>`, c),
    meet: (c) => svg(`<path d="M6 4h8a2 2 0 0 1 2 2v4a2 2 0 0 1-2 2H9l-3 2.5V12H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2Z" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/>`, c),
    unwind: (c) => svg(`<path d="M4 8h9v5a3 3 0 0 1-3 3H7a3 3 0 0 1-3-3V8Z" stroke="currentColor" stroke-width="1.5"/><path d="M13 9.5h1.5a2 2 0 0 1 0 4H13" stroke="currentColor" stroke-width="1.5"/><path d="M7 3.4c0 .8-.8 1-.8 1.8M9.6 3.4c0 .8-.8 1-.8 1.8" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/>`, c),
    heart: (c) => svg(`<path d="M10 16.3S3.6 12.5 3.6 8.1a3.8 3.8 0 0 1 6.4-2.8 3.8 3.8 0 0 1 6.4 2.8c0 4.4-6.4 8.2-6.4 8.2Z" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/>`, c),
    meh: (c) => svg(`<circle cx="10" cy="10" r="7" stroke="currentColor" stroke-width="1.5"/><path d="M7 12.2h6M7.5 8h.01M12.5 8h.01" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>`, c),
    nope: (c) => svg(`<path d="M5.5 5.5l9 9M14.5 5.5l-9 9" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>`, c),
    cart: (c) => svg(`<path d="M2.5 3h1.7l1.2 9.4A1.5 1.5 0 0 0 6.9 13.7h7.6a1.5 1.5 0 0 0 1.5-1.2l1-5.5H4.8" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round" stroke-linecap="round"/><circle cx="8" cy="17" r="1.15" fill="currentColor"/><circle cx="14.5" cy="17" r="1.15" fill="currentColor"/>`, c),
    soundOn: (c) => svg(`<path d="M4 8v4h3l4 3V5L7 8H4Z" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/><path d="M13.5 7.5a3.5 3.5 0 0 1 0 5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>`, c),
    soundOff: (c) => svg(`<path d="M4 8v4h3l4 3V5L7 8H4Z" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/><path d="M13 8l3.5 4M16.5 8 13 12" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>`, c),
    check: (c) => svg(`<path d="M4 10.3l3.4 3.4L16 5.3" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>`, c),
    plus: (c) => svg(`<path d="M10 4v12M4 10h12" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>`, c),
    arrowLeft: (c) => svg(`<path d="M12 4.5 6 10l6 5.5M6.5 10H16" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>`, c),
    spark: (c) => svg(`<path d="M10 2.5c.4 3 1.7 4.3 4.7 4.7-3 .4-4.3 1.7-4.7 4.7-.4-3-1.7-4.3-4.7-4.7 3-.4 4.3-1.7 4.7-4.7Z" fill="currentColor"/><path d="M16 13c.2 1.3.8 1.9 2.1 2.1-1.3.2-1.9.8-2.1 2.1-.2-1.3-.8-1.9-2.1-2.1 1.3-.2 1.9-.8 2.1-2.1Z" fill="currentColor"/>`, c),
    camera: (c) => svg(`<path d="M3 6.5A1.5 1.5 0 0 1 4.5 5h2l.8-1.5h5.4L13.5 5h2A1.5 1.5 0 0 1 17 6.5v7A1.5 1.5 0 0 1 15.5 15h-11A1.5 1.5 0 0 1 3 13.5v-7Z" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/><circle cx="10" cy="10" r="2.8" stroke="currentColor" stroke-width="1.5"/>`, c),
    warning: (c) => svg(`<path d="M10 3.5 17.5 16h-15L10 3.5Z" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/><path d="M10 8.5v3.2M10 13.8h.01" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>`, c),
    clock: (c) => svg(`<circle cx="10" cy="10" r="7" stroke="currentColor" stroke-width="1.5"/><path d="M10 6v4l3 2" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>`, c),
    checkCircle: (c) => svg(`<circle cx="10" cy="10" r="7.5" stroke="currentColor" stroke-width="1.5"/><path d="M6.5 10.2l2.3 2.3 4.7-5.2" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>`, c),
    smile: (c) => svg(`<circle cx="10" cy="10" r="7" stroke="currentColor" stroke-width="1.5"/><path d="M6.7 11.5c.8 1.1 2 1.7 3.3 1.7s2.5-.6 3.3-1.7M7.5 8h.01M12.5 8h.01" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>`, c),
    frown: (c) => svg(`<circle cx="10" cy="10" r="7" stroke="currentColor" stroke-width="1.5"/><path d="M6.7 13.2c.8-1.1 2-1.7 3.3-1.7s2.5.6 3.3 1.7M7.5 8h.01M12.5 8h.01" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>`, c),
  };
})();
