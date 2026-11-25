// Formspree form that emails hello@useondra.com. Public by design; override per environment.
export const DEMO_FORM_ENDPOINT = process.env.NEXT_PUBLIC_DEMO_FORM_ENDPOINT || "https://formspree.io/f/xeagnrre";
export const CONTACT_EMAIL = process.env.NEXT_PUBLIC_CONTACT_EMAIL || "hello@useondra.com";
export const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL || "https://useondra.com";
