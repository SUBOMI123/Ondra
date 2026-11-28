// Formspree form that emails hello@useondra.com. Public by design; override per environment.
export const DEMO_FORM_ENDPOINT = process.env.NEXT_PUBLIC_DEMO_FORM_ENDPOINT || "https://formspree.io/f/xeagnrre";
export const CONTACT_EMAIL = process.env.NEXT_PUBLIC_CONTACT_EMAIL || "hello@useondra.com";
export const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL || "https://useondra.com";
// The dealer dashboard (apps/web). "Sign in" links to its /login. Locally: http://localhost:3001.
// TODO: app.useondra.com isn't live until hosting is set up (docs/ARCHITECTURE.md).
export const APP_URL = process.env.NEXT_PUBLIC_APP_URL || "https://app.useondra.com";
export const SIGN_IN_URL = `${APP_URL}/login`;
// The business registered with US carriers for texting (the A2P 10DLC brand). Carriers check that the privacy policy
// and terms name it, so it must match the registration exactly. TODO(founder): set to the registered legal name.
export const BRAND_NAME = process.env.NEXT_PUBLIC_BRAND_NAME || "Ondra";
export const TEXT_NUMBER = "(707) 306-8599";
