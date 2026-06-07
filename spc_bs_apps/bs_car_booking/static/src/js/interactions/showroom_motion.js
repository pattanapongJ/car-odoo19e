/** @odoo-module **/
/* Lightweight showroom motion for catalog/detail/configurator pages. */

import { Interaction } from "@web/public/interaction";
import { registry } from "@web/core/registry";

export class ShowroomMotion extends Interaction {
    // #wrapwrap is the website content root present on every page. Using
    // "body" does not instantiate the interaction (the scanner roots below
    // <body>), which would leave every [data-bs-car-reveal] element hidden.
    static selector = "#wrapwrap";

    start() {
        // Mark the document JS-ready so the reveal styles only hide content
        // when this interaction is actually running (fail-safe: no JS = visible).
        document.documentElement.classList.add("o_car_reveal_ready");

        this.reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
        this.revealEls = Array.from(document.querySelectorAll("[data-bs-car-reveal]"));
        this.countEls = Array.from(document.querySelectorAll("[data-bs-count-to]"));

        if (!this.revealEls.length && !this.countEls.length) return;

        if (this.reducedMotion || !("IntersectionObserver" in window)) {
            for (const el of this.revealEls) el.classList.add("is-visible");
            for (const el of this.countEls) this._setFinalCount(el);
            return;
        }

        this.observer = new IntersectionObserver(
            (entries) => {
                for (const entry of entries) {
                    if (!entry.isIntersecting) continue;
                    entry.target.classList.add("is-visible");
                    if (entry.target.dataset.bsCountTo) {
                        this._animateCount(entry.target);
                    }
                    this.observer.unobserve(entry.target);
                }
            },
            { rootMargin: "0px 0px -12% 0px", threshold: 0.18 }
        );

        for (const el of this.revealEls) this.observer.observe(el);
        for (const el of this.countEls) this.observer.observe(el);

        this.registerCleanup(() => this.observer?.disconnect());
    }

    _setFinalCount(el) {
        const target = parseInt(el.dataset.bsCountTo || "0");
        if (!Number.isNaN(target)) el.textContent = target.toLocaleString();
    }

    _animateCount(el) {
        const target = parseInt(el.dataset.bsCountTo || "0");
        if (!target || Number.isNaN(target)) return;
        const start = performance.now();
        const duration = 900;
        const tick = (now) => {
            const progress = Math.min((now - start) / duration, 1);
            const eased = 1 - Math.pow(1 - progress, 3);
            el.textContent = Math.round(target * eased).toLocaleString();
            if (progress < 1) {
                requestAnimationFrame(tick);
            }
        };
        requestAnimationFrame(tick);
    }
}

registry
    .category("public.interactions")
    .add("bs_car_booking.showroom_motion", ShowroomMotion);
