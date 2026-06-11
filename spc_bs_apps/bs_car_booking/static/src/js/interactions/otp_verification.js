/** @odoo-module **/
/* ================================================================
   BS CAR BOOKING - OTP Verification Interaction (Odoo 19 OWL)
   Handles OTP digit inputs, countdown timer, verify & resend
   ================================================================ */

import { Interaction } from "@web/public/interaction";
import { registry } from "@web/core/registry";
import { initOtpDigits } from "@bs_car_booking/js/otp_digits";

export class OtpVerification extends Interaction {
    static selector = ".otp_form";

    setup() {
        this.countdownSecs = 300; // fallback; the card carries the real value
        this.countdownInterval = null;
        this.resendCooldown = 0;
        this.resendTimer = null;
    }

    start() {
        // Find booking ID from parent .otp_card element
        const card = this.el.closest("[data-booking-id]");
        const bookingId = parseInt(card?.dataset?.bookingId || "0");
        const accessToken = this.el.closest("[data-access-token]")?.dataset?.accessToken || "";
        if (!bookingId) return;
        // Real remaining lifetime rendered by the server (configurable expiry).
        const expiry = parseInt(card?.dataset?.otpExpiry || "0");
        if (expiry > 0) this.countdownSecs = expiry;
        this.fullExpiry = parseInt(card?.dataset?.otpExpiry || "0") || this.countdownSecs;
        // Resend cooldown follows the website setting (0 = no cooldown).
        this.resendSecs = parseInt(card?.dataset?.otpResend ?? "30");
        if (Number.isNaN(this.resendSecs) || this.resendSecs < 0) this.resendSecs = 30;

        const getEl = (id) => document.getElementById(id);
        const digitInputs = this.el.querySelectorAll(".otp_digit");
        const verifyBtn = getEl("otp_verify_btn");
        const resendBtn = getEl("otp_resend_btn");
        const resendLabel = getEl("otp_resend_label") || resendBtn;
        const countdownEl = getEl("otp_countdown");
        const errorMsgEl = getEl("otp_error_msg");
        const successMsgEl = getEl("otp_success_msg");

        // ── Helpers ────────────────────────────────────────
        const otpDigits = initOtpDigits(digitInputs);
        const getOtpCode = () => otpDigits.getCode();
        // Enable verify button only when all 6 digits are filled.
        if (verifyBtn) verifyBtn.disabled = true;
        const syncVerifyBtn = () => {
            if (verifyBtn) verifyBtn.disabled = getOtpCode().length !== 6;
        };
        digitInputs.forEach((inp) => inp.addEventListener("input", syncVerifyBtn));
        const showError = (msg) => {
            if (errorMsgEl) {
                errorMsgEl.textContent = msg;
                errorMsgEl.parentElement.classList.remove("d-none");
            }
            if (successMsgEl) successMsgEl.parentElement.classList.add("d-none");
        };
        const showSuccess = (msg) => {
            if (successMsgEl) {
                successMsgEl.textContent = msg;
                successMsgEl.parentElement.classList.remove("d-none");
            }
            if (errorMsgEl) errorMsgEl.parentElement.classList.add("d-none");
        };

        // ── Countdown Timer ────────────────────────────────
        const updateCountdown = () => {
            const mins = Math.floor(this.countdownSecs / 60);
            const secs = this.countdownSecs % 60;
            if (countdownEl) {
                countdownEl.textContent =
                    String(mins).padStart(2, "0") + ":" +
                    String(secs).padStart(2, "0");
            }
            if (this.countdownSecs <= 0) {
                clearInterval(this.countdownInterval);
                if (countdownEl) countdownEl.textContent = "Expired";
                if (verifyBtn) verifyBtn.disabled = true;
            }
            this.countdownSecs--;
        };
        this.countdownInterval = setInterval(updateCountdown, 1000);

        // ── Resend Cooldown (duration from the website setting) ──
        const startResendCooldown = (secs = this.resendSecs) => {
            if (!resendBtn) return;
            if (!secs) {
                resendBtn.disabled = false;
                resendLabel.textContent = "Resend Code";
                return;
            }
            if (this.resendTimer) clearInterval(this.resendTimer);
            resendBtn.disabled = true;
            this.resendCooldown = secs;
            resendLabel.textContent = "Resend in " + secs + "s";
            this.resendTimer = setInterval(() => {
                this.resendCooldown--;
                if (this.resendCooldown <= 0) {
                    clearInterval(this.resendTimer);
                    resendLabel.textContent = "Resend Code";
                    resendBtn.disabled = false;
                } else {
                    resendLabel.textContent = "Resend in " + this.resendCooldown + "s";
                }
            }, 1000);
        };
        startResendCooldown();

        // ── Verify OTP ─────────────────────────────────────
        if (verifyBtn) {
            verifyBtn.addEventListener("click", async () => {
                const code = getOtpCode();
                if (code.length !== 6) {
                    showError("Please enter the complete 6-digit code.");
                    return;
                }
                verifyBtn.disabled = true;
                verifyBtn.innerHTML = '<i class="fa fa-spinner fa-spin"></i> Verifying...';

                try {
                    const r = await fetch("/car_booking/booking/otp/verify", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({
                            jsonrpc: "2.0",
                            method: "call",
                            params: {
                                booking_id: bookingId,
                                access_token: accessToken,
                                otp_code: code,
                            },
                        }),
                    });
                    const data = await r.json();
                    const result = data.result;
                    if (result?.success) {
                        showSuccess("Phone verified! Redirecting...");
                        setTimeout(() => {
                            window.location.href = result.redirect_url;
                        }, 1500);
                    } else {
                        showError(result?.error || "Invalid code.");
                        verifyBtn.disabled = false;
                        verifyBtn.innerHTML = '<i class="fa fa-check"></i> Verify';
                        digitInputs.forEach((inp) => (inp.value = ""));
                        digitInputs[0]?.focus();
                    }
                } catch {
                    showError("Network error. Please try again.");
                    verifyBtn.disabled = false;
                    verifyBtn.innerHTML = '<i class="fa fa-check"></i> Verify';
                }
            });
        }

        // ── Resend OTP ─────────────────────────────────────
        const resendOtp = async (channel) => {
            const r = await fetch("/car_booking/booking/otp/resend", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    jsonrpc: "2.0",
                    method: "call",
                    params: {
                        booking_id: bookingId,
                        access_token: accessToken,
                        channel: channel || null,
                    },
                }),
            });
            const data = await r.json();
            return data.result || {};
        };

        if (resendBtn) {
            resendBtn.addEventListener("click", async () => {
                if (this.resendCooldown > 0) return;
                resendBtn.disabled = true;
                resendBtn.textContent = "Sending...";

                try {
                    const result = await resendOtp(null);
                    if (result.success) {
                        this.countdownSecs = result.expires_in || this.fullExpiry;
                        if (countdownEl) {
                            const m = Math.floor(this.countdownSecs / 60);
                            const s = this.countdownSecs % 60;
                            countdownEl.textContent =
                                String(m).padStart(2, "0") + ":" + String(s).padStart(2, "0");
                        }
                        if (verifyBtn) verifyBtn.disabled = false;
                        startResendCooldown(result.resend_in ?? this.resendSecs);
                        showSuccess("New code sent!");
                        digitInputs.forEach((inp) => (inp.value = ""));
                        digitInputs[0]?.focus();
                        syncVerifyBtn();
                    } else {
                        showError(result.error || "Failed to resend. Please try again.");
                        if (this.resendCooldown <= 0) {
                            resendBtn.disabled = false;
                            resendBtn.textContent = "Resend Code";
                        }
                    }
                } catch {
                    showError("Network error. Please try again.");
                    if (this.resendCooldown <= 0) {
                        resendBtn.disabled = false;
                        resendBtn.textContent = "Resend Code";
                    }
                }
            });
        }

        // ── Switch delivery channel (customer-choice websites) ──
        const switchBtn = getEl("otp_switch_btn");
        if (switchBtn) {
            switchBtn.addEventListener("click", async () => {
                const channel = switchBtn.dataset.channel;
                if (!channel) return;
                switchBtn.disabled = true;
                switchBtn.textContent = "Sending...";
                try {
                    const result = await resendOtp(channel);
                    if (result.success) {
                        // Reload so the page copy reflects the new channel
                        // (icon, title, destination, switch direction).
                        window.location.reload();
                    } else {
                        showError(result.error || "Could not switch. Please try again.");
                        switchBtn.disabled = false;
                        switchBtn.textContent = channel === "email"
                            ? "Send to my email instead" : "Send by SMS instead";
                    }
                } catch {
                    showError("Network error. Please try again.");
                    switchBtn.disabled = false;
                }
            });
        }

        this.registerCleanup(() => {
            if (this.countdownInterval) clearInterval(this.countdownInterval);
            if (this.resendTimer) clearInterval(this.resendTimer);
        });
    }
}

registry
    .category("public.interactions")
    .add("bs_car_booking.otp_verification", OtpVerification);
