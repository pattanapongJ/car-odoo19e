/** @odoo-module **/
/* Catalog page interactions: scroll-reveal animations + sticky filter bar.
   - Scroll reveal: IntersectionObserver adds .is-revealed to [data-bs-reveal]
     elements as they enter the viewport. Cards get staggered per their index.
   - Sticky filter: watches the filter bar's sticky state and toggles .is-stuck
     for a subtle shadow when the bar is pinned. */

import { Interaction } from "@web/public/interaction";
import { registry } from "@web/core/registry";

export class CatalogMotion extends Interaction {
    static selector = ".bs_catalog_band";

    setup() {
        this._observer = null;
        this._sentinel = null;
        this._stickyEl = null;
    }

    start() {
        this._initReveal();
        this._initSticky();
    }

    /* ── Scroll reveal via IntersectionObserver ────────────────────── */
    _initReveal() {
        const reveals = this.el.querySelectorAll("[data-bs-reveal]");
        if (!reveals.length) return;

        // Index cards so we can stagger them via CSS --bs-reveal-i.
        let cardIndex = 0;
        reveals.forEach((el) => {
            if (el.classList.contains("bs_catalog_card")) {
                el.style.setProperty("--bs-reveal-i", cardIndex++);
            }
        });

        // Only hide elements after JS confirms it can control them.
        // (No-JS fallback: elements are fully visible.)
        this.el.classList.add("bs-reveal-ready");

        this._observer = new IntersectionObserver(
            (entries) => {
                entries.forEach((entry) => {
                    if (entry.isIntersecting) {
                        entry.target.classList.add("is-revealed");
                        this._observer.unobserve(entry.target);
                    }
                });
            },
            { threshold: 0.12, rootMargin: "0px 0px -20px 0px" }
        );

        reveals.forEach((el) => this._observer.observe(el));
    }

    /* ── Sticky filter bar state ───────────────────────────────────── */
    _initSticky() {
        const sticky = this.el.querySelector("[data-bs-filter-sticky]");
        if (!sticky) return;

        // Insert a zero-height sentinel just above the sticky bar so we can
        // detect when the bar has left its natural position.
        this._sentinel = document.createElement("div");
        this._sentinel.style.cssText = "position:absolute;height:0;width:0";
        sticky.parentNode.insertBefore(this._sentinel, sticky);
        this._stickyEl = sticky;

        this._stickyObserver = new IntersectionObserver(
            ([entry]) => {
                // When the sentinel scrolls out of view, the sticky bar is pinned.
                sticky.classList.toggle("is-stuck", !entry.isIntersecting);
            },
            { threshold: 0 }
        );

        this._stickyObserver.observe(this._sentinel);
    }

    destroy() {
        if (this._observer) {
            this._observer.disconnect();
            this._observer = null;
        }
        if (this._stickyObserver) {
            this._stickyObserver.disconnect();
            this._stickyObserver = null;
        }
        if (this._sentinel && this._sentinel.parentNode) {
            this._sentinel.parentNode.removeChild(this._sentinel);
        }
        super.destroy();
    }
}

registry.category("public.interactions").add("bs_catalog_motion", CatalogMotion);

/* ── Hero reveal (same pattern, for .bs_catalog_hero elements) ──── */
export class HeroMotion extends Interaction {
    static selector = ".bs_catalog_hero";

    setup() {
        this._observer = null;
    }

    start() {
        const reveals = this.el.querySelectorAll("[data-bs-reveal]");
        if (!reveals.length) return;

        this.el.classList.add("bs-reveal-ready");

        this._observer = new IntersectionObserver(
            (entries) => {
                entries.forEach((entry) => {
                    if (entry.isIntersecting) {
                        entry.target.classList.add("is-revealed");
                        this._observer.unobserve(entry.target);
                    }
                });
            },
            { threshold: 0.08, rootMargin: "0px 0px -10px 0px" }
        );

        reveals.forEach((el) => this._observer.observe(el));
    }

    destroy() {
        if (this._observer) {
            this._observer.disconnect();
            this._observer = null;
        }
        super.destroy();
    }
}

registry.category("public.interactions").add("bs_hero_motion", HeroMotion);

/* ── Detail page motion ───────────────────────────────────────────
   Reuses the catalog reveal (sticky init is a no-op: no filter bar on
   the detail page) and opens the full-spec <details> accordion when a
   #full_specs anchor is followed, so the jump never lands on a
   collapsed sheet. */
export class DetailMotion extends CatalogMotion {
    static selector = ".bs_detail_page";

    start() {
        super.start();
        this._initSpecsAnchor();
    }

    _initSpecsAnchor() {
        const details = this.el.querySelector("#full_specs details");
        if (!details) return;
        this.el.querySelectorAll('a[href="#full_specs"]').forEach((a) => {
            const onClick = () => {
                details.open = true;
            };
            a.addEventListener("click", onClick);
            this.registerCleanup(() => a.removeEventListener("click", onClick));
        });
    }
}

registry.category("public.interactions").add("bs_detail_motion", DetailMotion);
