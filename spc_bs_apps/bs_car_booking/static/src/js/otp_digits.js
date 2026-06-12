/** @odoo-module **/
/* Shared 6-digit OTP input behaviour: auto-advance, backspace to previous,
   paste distribution. Used by the funnel verify page so
   both render the same code-entry UI. */

export function initOtpDigits(inputs) {
    const digits = Array.from(inputs || []);
    digits.forEach((input, idx) => {
        input.addEventListener("input", () => {
            const val = input.value.replace(/[^0-9]/g, "");
            input.value = val.slice(0, 1);
            if (val && idx < digits.length - 1) digits[idx + 1].focus();
        });
        input.addEventListener("keydown", (e) => {
            if (e.key === "Backspace" && !input.value && idx > 0) {
                digits[idx - 1].focus();
            }
        });
    });
    digits[0]?.addEventListener("paste", (e) => {
        e.preventDefault();
        const paste = (
            (e.clipboardData || window.clipboardData).getData("text") || ""
        ).replace(/[^0-9]/g, "");
        paste.split("").slice(0, digits.length).forEach((ch, i) => {
            if (digits[i]) digits[i].value = ch;
        });
    });
    return {
        getCode: () => digits.map((d) => d.value).join(""),
        clear: () => digits.forEach((d) => (d.value = "")),
        focus: () => digits[0]?.focus(),
    };
}
