/** @odoo-module **/
/* Dealer locator: click (or keyboard-activate) a showroom card to recentre the
   embedded map on that dealer. The first card is active by default; the map is
   a keyless Google Maps embed (one location at a time), so we swap its src. */

import { Interaction } from "@web/public/interaction";
import { registry } from "@web/core/registry";

export class DealerLocator extends Interaction {
    static selector = ".bs_dealers_locator";

    start() {
        this.map = this.el.querySelector(".bs_dealers_map");
        this.cards = Array.from(this.el.querySelectorAll(".bs_dealer_card[data-map-src]"));
        if (!this.map || this.cards.length < 2) {
            return; // nothing to switch between
        }
        this.cards.forEach((card) => {
            card.addEventListener("click", () => this._focus(card));
            card.addEventListener("keydown", (ev) => {
                if (ev.key === "Enter" || ev.key === " ") {
                    ev.preventDefault();
                    this._focus(card);
                }
            });
        });
    }

    _focus(card) {
        const src = card.dataset.mapSrc;
        if (src && this.map.getAttribute("src") !== src) {
            this.map.setAttribute("src", src);
        }
        this.cards.forEach((c) => c.classList.toggle("is_active", c === card));
        if (window.matchMedia("(max-width: 991.98px)").matches) {
            this.map.scrollIntoView({ behavior: "smooth", block: "center" });
        }
    }
}

registry.category("public.interactions").add("bs_car_booking.dealer_locator", DealerLocator);
