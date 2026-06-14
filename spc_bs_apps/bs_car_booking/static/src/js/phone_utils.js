/** @odoo-module **/
/* Phone validation shared by the configurator.
   Mirrors the server rule (bs.car.booking PHONE_RE): after stripping spaces,
   dashes, dots and parentheses → optional +, then 7-15 digits. */

export function normalizePhone(value) {
    return (value || "").replace(/[\s\-().]/g, "");
}

export function isValidPhone(value) {
    return /^\+?\d{7,15}$/.test(normalizePhone(value));
}
