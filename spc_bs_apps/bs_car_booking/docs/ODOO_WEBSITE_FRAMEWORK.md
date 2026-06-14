# Odoo 19 Website Framework — Developer & Functional Reference
### Studied from core: `addons/web`, `addons/portal`, `addons/website` (+ theme howto)

> A working reference for building/maintaining website modules like `bs_car_booking`.
> File:line citations point into the Odoo 19 source at `/home/tmw/odoo_source/19c`.

---

## A. The render chain (every frontend page)

```
web.layout (web/views/webclient_templates.xml:17)            <!DOCTYPE>, <head>, CSRF
  └─ web.frontend_layout (…:38)                              #wrapwrap, <header id="top">,
        │                                                     <main>, <footer id="bottom"><div id="footer">,
        │                                                     assets_frontend(css) + _minimal/_lazy(js)
        └─ portal.frontend_layout (portal/views/portal_templates.xml:3)   RTL, .o_portal, skip-link, OG/Twitter
              └─ website.layout (website/views/website_templates.xml:81)  data-website-id/editable, title+SEO,
                                                                          analytics, header/footer color+overlay,
                                                                          o_header_overlay, page options
```
- The base `<header id="top">` ships with **only a logo**; the active **header template** replaces `//header//nav`.
- `#footer` is an `oe_structure` (editable drop zone); `.o_footer_copyright` is a separate bar.
- Key classes the scroll JS needs: `header#top` + `o_header_standard` (see `header_standard.js`).

---

## B. Data layer

### Core models
| Model | File | Purpose / key fields |
|---|---|---|
| `website` | website/models/website.py:99 | domain, default_lang_id, language_ids, **homepage_url**, company_id, theme_id, social_*, logo/favicon, analytics, cookies_bar. `website_domain()` → `('website_id','in',[False,*ids])` |
| `website.page` | website_page.py:24 | url, view_id (`_inherits` ir.ui.view), **is_homepage** (computed), is_published, website_indexed, date_publish, response caching (`_get_response`, 3600s TTL) |
| `website.menu` | website_menu.py:15 | name, url (computed, `#` for containers), parent_id/child_id (max 2 levels), sequence, website_id, mega_menu_content, group_ids, `_is_active()` |
| `website.rewrite` | website_rewrite.py:60 | url_from→url_to redirects: 301/302/308/404 |
| `website.controller.page` | website_controller_page.py:7 | model-driven listing pages (`/model/<name>`), record_domain, default_layout grid/list |

### Multi-website + COW (copy-on-write) — the most important concept
- Generic records have `website_id = False` (shared by all sites). Editing **in a website context** forks a website-specific copy.
- Trigger: `.with_context(website_id=ID).write(...)` on **`ir.ui.view`** (ir_ui_view.py:93) and **`ir.asset`** (ir_asset.py:77). `no_cow=True` bypasses it.
- `filter_duplicate()` keeps the most specific record per `key` per website.
- **Implication:** a generic view you ship can be silently forked per website when an admin edits it in the builder → two records with the same `key`, one per site. This is exactly what broke our header (two active `//header//nav` replacers).

### Theme content models (`theme.*`)
- `theme.ir.ui.view`, `theme.ir.asset`, `theme.website.page`, `theme.website.menu`, `theme.ir.attachment` (theme_models.py).
- On theme install, `ir_module_module._theme_load → _update_records` **copies** them into the real models per website (with a `theme_template_id` backref), honoring `noupdate`. This is how theme content becomes **per-website + builder-editable** instead of static module data.

### Publishing & access
- `website.published.mixin` / `website.published.multi.mixin` (mixins.py:201/275): `is_published`/`website_published`, `can_publish`, `website_url` (override per model). Multi-mixin: published-on-site = `is_published AND (website_id is False OR == current)`.
- `website.seo.metadata` (mixins.py:19): meta title/description/keywords/OG, `is_seo_optimized`.
- View `visibility`: Public / Connected / Restricted group / Password (`ir_ui_view._handle_visibility`).

---

## C. Rendering / theming

### Header & footer = mutually-exclusive selectable templates
- Header family (website_templates.xml): `template_header_default` (active), `_hamburger`, `_stretch`, `_vertical`, `_search`, `_sales_one..four`, `_sidebar`, `_boxed` (+ `_align_center/right` variants). **Only one active at a time**; each inherits `website.layout` and replaces `//header//nav` with a `t-call="website.navbar"`.
- Footer family: `footer_custom` (active) + `template_footer_descriptive/centered/links/minimalist/contact/.../mega*`.
- Reusable pieces: `website.navbar`, `website.navbar_nav`, `website.submenu`, and `placeholder_header_{brand,search_box,language_selector,text_element,social_links,call_to_action}`, `portal.placeholder_user_sign_in`, `portal.user_dropdown`, `template_header_mobile` (offcanvas).
- **Correct way to add a custom header:** ship it as another selectable `template_header_*` (inherit website.layout, replace `//header//nav`) and make it the site's active header — NOT a force-override.

### Assets & SCSS
- Frontend bundles: `web.assets_frontend` (CSS), `web.assets_frontend_minimal` + `_lazy` (JS). Declared/overridden via **`ir.asset`** records (directive: append/prepend/before/after/replace/remove/include; bundle; path; target).
- Theming variables in `web._assets_primary_variables`: `primary_variables.scss` defines `$o-color-palettes`, `$o-theme-font-configs`, `$o-grays`, `$o-brand-*`, fonts, spacing. A theme overrides these to restyle globally.
- Color-combination system: `o_cc` + `o_cc1..5` on sections/header/footer; header color/overlay via page options (`header_color`, `header_text_color`, `header_overlay`).

### Snippets
- Defined as `s_*` templates (website/views/snippets/*.xml) with `data-snippet`, `data-name`, `o_cc*`. Registered in snippets.xml (`t-snippet`).
- Options live in builder plugin XML (`<BuilderRow>/<BuilderSelect>/<BuilderButton>/<BuilderCheckbox>` with `classAction`, `dataAttributeAction`, `applyTo`).
- Drop zones: `.oe_structure` (`_solo`, `_inline`, `oe_unremovable`). Editables: `contenteditable`, `data-oe-*`.

### Frontend interactivity — `public.interactions`
- Base: `@web/public/interaction` `Interaction` (web/static/src/public/interaction.js). `static selector`, `setup()`, `willStart()`, `start()`, `destroy()`, `dynamicContent` (`t-on-*`, `t-att-*`), `registerCleanup`, `waitFor`, `debounce`.
- Registered via `registry.category("public.interactions").add(name, Class)`. One instance per matched element; auto start/destroy. (This is exactly what our `home_showcase.js` / `booking_tracking.js` use.)

---

## D. Routing · SEO · i18n · Portal

### Request flow (`website/models/ir_http.py`)
- `_match` → `get_current_website()`; `_frontend_pre_dispatch` sets `request.website`, `website_id` context, allowed_company_ids, lang/tz.
- `website=True` routes render in website context; `auth='public'` runs as `website.user_id` when logged out.
- Homepage `/` (controllers/main.py:89): if `homepage_url` set & != `/`, reroute to it; else serve the `/` website.page; else first menu child; else 404.
- Multi-website: matched by `website.domain` (punycode/port-aware) or session `force_website_id` (`/website/force/<id>`).

### SEO
- `website.seo.metadata` meta fields; `/sitemap.xml` enumerates published pages + `sitemap=True` controller routes (`_enumerate_pages`, website.py:1546); `/robots.txt`; canonical + hreflang alternates in website.layout head.

### i18n (frontend)
- `request.lang` / `lang.url_code`; URL prefix `/<url_code>/<path>`; `/website/lang/<lang>` switches + sets `frontend_lang` cookie; languages from `website.language_ids` (activate `res.lang` first). `url_localized` builds alternates.

### Portal (`addons/portal`)
- `CustomerPortal` (controllers/portal.py): `/my`, `/my/home`, `_prepare_home_portal_values(counters)` (badges), `_prepare_portal_layout_values`, `pager()`.
- `portal.mixin` (models/portal_mixin.py): `access_url` (override `_compute_access_url`), `access_token` (UUID), `_portal_ensure_token`, `get_portal_url`, `_get_share_url`, `_document_check_access`. ← our booking tracking rides entirely on this.

---

## E. Functional (what a consultant/admin does in the Website app)
- **Site ▸ Pages / Menus** — create pages, set **Is Homepage**, edit nav (drag hierarchy, mega menus).
- **Builder (Edit)** — drag snippets, Customize panel (layout/colors/typography/spacing/effects), **Theme tab** (palette, fonts, backgrounds), assets editor (custom SCSS/JS in `user_custom_*`).
- **Configuration ▸ Settings** — domain, languages, social links, analytics/SEO keys, cookies bar, block third-party domains.
- **Themes** — install a `theme_*` module; its `theme.*` content copies onto the site.
- **Publish** toggle, SEO popup (title/description/keywords/OG, slug), website switcher (multi-website).

---

## F. Practical takeaways for `bs_car_booking`

What the framework study tells us to do (and what we did pragmatically):

1. **Header — prefer a selectable template over a force-override.**
   We replace the whole `<header>` at priority 999 to dodge the COW double-nav crash. The *framework-correct* approach is to ship `template_header_<brand>` (inherit website.layout, replace `//header//nav`) and set it as the website's **active** header so COW treats it like any standard header. Trade-off: our override is bullet-proof but bypasses the builder's header selector. Revisit if we want the brand header to be builder-switchable.

2. **Adopt `primary_variables.scss` for brand colour/fonts.**
   Our `--car-*` CSS vars are hard-coded. Overriding `$o-color-palettes` / `$o-theme-font-configs` (in `web._assets_primary_variables`) would make brand styling builder-configurable and consistent with `o_cc*` sections.

3. **Use `ir.asset` records (not just the manifest assets list)** when we need website-specific or directive-based asset control (append/replace/before).

4. **Tracking/portal is already framework-aligned** — we reuse `portal.mixin` (`access_token`, `_compute_access_url`, `get_portal_url`) and `public.interactions`. Good.

5. **Content as `theme.*` (optional, bigger refactor):** if the Hongqi visual content should be per-website + builder-editable, a separate `bs_car_theme` module using `theme.ir.ui.view`/`theme.website.page`/`theme.website.menu` is the canonical split — `bs_car_booking` keeps the commerce/booking logic.

6. **COW awareness:** any generic view we ship can be forked per website once edited in the builder. Keep `key`s stable and avoid multiple active views competing on the same xpath (the root cause of our header crash).

---
*Reference compiled from Odoo 19 core for the bs_car_booking project.*
