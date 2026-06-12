/** @odoo-module **/
/* Public booking-tracking form: reference + phone -> one-time code -> redirect
   to the token-gated status page. Mirrors the funnel OTP fetch/JSON-RPC style. */

import { Interaction } from "@web/public/interaction";
import { registry } from "@web/core/registry";
import { initOtpDigits } from "@bs_car_booking/js/otp_digits";
import { isValidPhone } from "@bs_car_booking/js/phone_utils";

export class BookingTracking extends Interaction {
    static selector = "#bs_track";

    setup() {
        this.refEl = this.el.querySelector("[data-track-ref]");
        this.phoneEl = this.el.querySelector("[data-track-phone]");
        this.msgEl = this.el.querySelector("[data-track-msg]");
        this.stepLookup = this.el.querySelector('[data-track-step="lookup"]');
        this.stepOtp = this.el.querySelector('[data-track-step="otp"]');
        this.timerWrap = this.el.querySelector("[data-track-timer-row]");
        this.countdownInterval = null;
        this.resendBtn = this.el.querySelector("[data-track-resend]");
        this.resendLabel = this.el.querySelector("[data-track-resend-label]");
    }

    start() {
        // Same 6-box entry behaviour as the funnel verify page.
        this.otpDigits = initOtpDigits(this.el.querySelectorAll(".otp_digit"));
        // Verify button: enabled only when all 6 digits are filled.
        this.verifyBtn = this.el.querySelector("[data-track-verify]");
        this._syncVerifyBtn();
        this.el.querySelectorAll(".otp_digit").forEach((inp) => {
            inp.addEventListener("input", () => this._syncVerifyBtn());
            inp.addEventListener("paste", (e) => {
                this._syncVerifyBtn();
            });
        });
        this._bind("[data-track-send]", () => this._lookup());
        this._bind("[data-track-verify]", () => this._verify());
        this._bind("[data-track-resend]", () => this._resend());
        // Enter key submits the active step.
        this.refEl?.addEventListener("keydown", (e) => e.key === "Enter" && this._lookup());
        this.phoneEl?.addEventListener("keydown", (e) => e.key === "Enter" && this._lookup());
        this.el.querySelectorAll(".otp_digit").forEach((d) =>
            d.addEventListener("keydown", (e) => e.key === "Enter" && this._verify()));
        this.registerCleanup(() => {
            if (this.countdownInterval) clearInterval(this.countdownInterval);
        });
    }

    /* The expiry countdown lives inside the resend button (same design as the
       funnel verify page): "Resend in mm:ss" while the code is valid (disabled),
       "Resend code" once it expires (enabled). Driven by expires_in. */
    _startCountdown(seconds) {
        if (!this.resendBtn || !seconds) return;
        if (this.countdownInterval) clearInterval(this.countdownInterval);
        this.timerWrap?.classList.remove("d-none");
        const labelEl = this.resendLabel || this.resendBtn;
        const end = Date.now() + seconds * 1000;
        const tick = () => {
            const left = Math.max(0, Math.round((end - Date.now()) / 1000));
            if (left <= 0) {
                clearInterval(this.countdownInterval);
                this.countdownInterval = null;
                this.resendBtn.disabled = false;
                labelEl.textContent = "Resend code";
                return;
            }
            this.resendBtn.disabled = true;
            const m = String(Math.floor(left / 60)).padStart(2, "0");
            const s = String(left % 60).padStart(2, "0");
            labelEl.textContent = `Resend in ${m}:${s}`;
        };
        tick();
        this.countdownInterval = setInterval(tick, 1000);
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
        if (!reference) {
            this._msg("Please enter your booking reference (e.g. CBK/2026/06/00042).", "error");
            this.refEl?.focus();
            return;
        }
        if (!isValidPhone(phone)) {
            this._msg("Please enter a valid phone number — the one used on the booking (7–15 digits).", "error");
            this.phoneEl?.focus();
            return;
        }
        this._busy(true);
        try {
            const res = await this._call("/track/lookup", { reference, phone });
            // Always a generic reply (anti-enumeration) — advance to the code step.
            this.stepLookup?.classList.add("d-none");
            this.stepOtp?.classList.remove("d-none");
            this._msg(res.message || "If a booking matches, a code has been sent.", "ok");
            this._startCountdown(res.expires_in);
            this.otpDigits?.focus();
        } catch {
            this._msg("Something went wrong. Please try again.", "error");
        } finally {
            this._busy(false);
        }
    }

    async _verify() {
        const code = (this.otpDigits?.getCode() || "").trim();
        if (code.length !== 6) {
            this._msg("Enter the 6-digit code you received.", "error");
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
        if (this.resendBtn?.disabled) return;
        this._busy(true);
        try {
            const res = await this._call("/track/resend", {});
            this._msg(res.message || "A new code has been sent.", res.ok === false ? "error" : "ok");
            if (res.ok !== false) {
                this.otpDigits?.clear();
                this.otpDigits?.focus();
                this._syncVerifyBtn();
                this._startCountdown(res.expires_in);
            }
        } catch {
            this._msg("Something went wrong. Please try again.", "error");
        } finally {
            this._busy(false);
        }
    }

    _syncVerifyBtn() {
        if (this.verifyBtn) {
            this.verifyBtn.disabled = (this.otpDigits?.getCode() || "").length !== 6;
        }
    }
}

registry.category("public.interactions").add("bs_car_booking.booking_tracking", BookingTracking);


