/** @odoo-module **/
/* Location locator: click (or keyboard-activate) a location card to recentre
   the keyless Google Maps embed on that location. The first card is active by
   default; the map is a single-pin embed, so we just swap its src. No API key. */

import { Interaction } from "@web/public/interaction";
import { registry } from "@web/core/registry";

export class DealerLocator extends Interaction {
    static selector = ".bs_dealers_locator";

    start() {
        this.map = this.el.querySelector(".bs_dealers_map_google");
        this.cards = Array.from(this.el.querySelectorAll(".bs_dealer_card[data-embed]"));
        if (!this.map || this.cards.length < 2) {
            return; // nothing to switch between
        }
        this.cards.forEach((card) => {
            this.addListener(card, "click", (ev) => {
                if (ev.target.closest("a")) {
                    return; // let the "Directions" link do its own thing
                }
                this._focus(card);
            });
            this.addListener(card, "keydown", (ev) => {
                if (ev.key === "Enter" || ev.key === " ") {
                    ev.preventDefault();
                    this._focus(card);
                }
            });
        });
    }

    _focus(card) {
        const src = card.dataset.embed;
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
