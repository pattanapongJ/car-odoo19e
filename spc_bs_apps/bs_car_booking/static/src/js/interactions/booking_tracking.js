/** @odoo-module **/
/* Public booking-tracking form: reference + phone -> one-time code -> redirect
   to the token-gated status page. Mirrors the funnel OTP fetch/JSON-RPC style. */

import { Interaction } from "@web/public/interaction";
import { registry } from "@web/core/registry";

export class BookingTracking extends Interaction {
    static selector = "#bs_track";

    setup() {
        this.refEl = this.el.querySelector("[data-track-ref]");
        this.phoneEl = this.el.querySelector("[data-track-phone]");
        this.codeEl = this.el.querySelector("[data-track-code]");
        this.msgEl = this.el.querySelector("[data-track-msg]");
        this.stepLookup = this.el.querySelector('[data-track-step="lookup"]');
        this.stepOtp = this.el.querySelector('[data-track-step="otp"]');
    }

    start() {
        this._bind("[data-track-send]", () => this._lookup());
        this._bind("[data-track-verify]", () => this._verify());
        this._bind("[data-track-resend]", () => this._resend());
        // Enter key submits the active step.
        this.refEl?.addEventListener("keydown", (e) => e.key === "Enter" && this._lookup());
        this.phoneEl?.addEventListener("keydown", (e) => e.key === "Enter" && this._lookup());
        this.codeEl?.addEventListener("keydown", (e) => e.key === "Enter" && this._verify());
    }

    _bind(sel, fn) {
        const el = this.el.querySelector(sel);
        if (el) {
            el.addEventListener("click", fn);
        }
    }

    async _call(url, params) {
        const r = await fetch(url, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ jsonrpc: "2.0", method: "call", params }),
        });
        const data = await r.json();
        return data.result || {};
    }

    _msg(text, kind) {
        if (!this.msgEl) {
            return;
        }
        this.msgEl.textContent = text || "";
        this.msgEl.classList.toggle("d-none", !text);
        this.msgEl.classList.toggle("is-error", kind === "error");
        this.msgEl.classList.toggle("is-ok", kind === "ok");
    }

    _busy(on) {
        this.el.classList.toggle("bs_track_busy", !!on);
    }

    async _lookup() {
        const reference = (this.refEl?.value || "").trim();
        const phone = (this.phoneEl?.value || "").trim();
        if (!reference || phone.length < 7) {
            this._msg("Please enter your booking reference and phone number.", "error");
            return;
        }
        this._busy(true);
        try {
            const res = await this._call("/track/lookup", { reference, phone });
            // Always a generic reply (anti-enumeration) — advance to the code step.
            this.stepLookup?.classList.add("d-none");
            this.stepOtp?.classList.remove("d-none");
            this._msg(res.message || "If a booking matches, a code has been sent.", "ok");
            this.codeEl?.focus();
        } catch {
            this._msg("Something went wrong. Please try again.", "error");
        } finally {
            this._busy(false);
        }
    }

    async _verify() {
        const code = (this.codeEl?.value || "").trim();
        if (code.length < 4) {
            this._msg("Enter the code from your phone.", "error");
            return;
        }
        this._busy(true);
        try {
            const res = await this._call("/track/verify", { code });
            if (res.success && res.redirect_url) {
                window.location.href = res.redirect_url;
                return;
            }
            this._msg(res.error || "Invalid code. Please try again.", "error");
        } catch {
            this._msg("Something went wrong. Please try again.", "error");
        } finally {
            this._busy(false);
        }
    }

    async _resend() {
        this._busy(true);
        try {
            const res = await this._call("/track/resend", {});
            this._msg(res.message || "A new code has been sent.", res.ok === false ? "error" : "ok");
        } catch {
            this._msg("Something went wrong. Please try again.", "error");
        } finally {
            this._busy(false);
        }
    }
}

registry.category("public.interactions").add("bs_car_booking.booking_tracking", BookingTracking);
