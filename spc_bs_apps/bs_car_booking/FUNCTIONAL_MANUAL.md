# Car Dealer Website — Configuration & Operations Manual
### Hongqi Thailand · for functional consultants & business analysts

**About this manual.** This guide is written in plain language for the people who *set up and run* the site — functional consultants, business analysts, and site administrators. It explains **what the system does** and **how to configure it, step by step**, using the names and menus exactly as they appear on screen. You do not need any programming knowledge. A short technical appendix at the end is marked clearly for your IT team.

---

## 1. What this system does (business overview)

This is a premium car‑dealership website. A customer can:

1. **Browse** car models, view photos, specifications, colours and stories.
2. **Build their car** — choose a trim, exterior colour, interior, wheels and add‑ons, and see the price update live.
3. **Choose a showroom (dealer)** and **verify their mobile number** by SMS code.
4. **Enter their details** and **pay a booking deposit** online.
5. **Track their booking** afterwards by logging in to *My Account*.

Behind the scenes, when a deposit is paid the system automatically creates a **real sales order**, a **deposit invoice**, and records the **payment** — so your sales and finance teams work with normal Odoo documents, not a separate silo. Reception/sales staff manage every booking from one screen and move it through its lifecycle (Confirmed → In Production → Ready → Delivered).

**In short:** marketing catalog → customer configures & books → deposit paid → sales order + invoice + payment created → booking tracked to delivery.

---

## 2. Before you start

- The **Car Booking** application must be installed (your IT team does this).
- **Decide on starting content.** The site can be installed two ways:
  - **With sample content** (recommended for demos/training): comes pre‑loaded with example Hongqi cars, showrooms and stories so every page looks complete immediately.
  - **Empty** (typical for a brand‑new live site): the catalog starts blank and **you create your own cars** using Section 4. *If the catalog is empty, the home page will look empty too* — so either load the sample content or add at least one published car before launch. Ask IT which way your site was installed.

Everything you configure lives under one top menu: **Car Booking** (with sub‑menus **Master Data** and **Bookings**).

---

## 3. STEP 1 — Company, currency & tax *(do this first)*

> Every car you create takes its **price currency** and **VAT** from your company settings. So configure the company **before** creating cars, otherwise prices and tax on the products will be wrong.

1. **Set the company currency to THB (Thai Baht).**
   *Settings ▸ Users & Companies ▸ Companies* → open your Thailand company → set Currency = **THB**.
2. **Point the website to the Thailand company.**
   *Website ▸ Configuration ▸ Settings ▸ Company* → select the Thailand company.
3. **Load the chart of accounts for the Thailand company.** *(This is essential — and the most common thing teams forget.)* With the Thailand company selected, open **Accounting ▸ Configuration ▸ Settings** and set the **Fiscal Localization / Accounting Package** to **Thailand**, then let it install. This creates the company’s own accounts, taxes and journals.
   > ⚠️ **Why this matters:** if the chart of accounts is not loaded, the company has no receivable/income accounts of its own. When a customer pays a deposit, the system cannot create the deposit invoice/payment and the payment page shows a *server error*. A chart can only be loaded while the company has no posted accounting entries — so do it before going live.
4. **Make sure a 7% VAT (sales tax) exists** (the Thailand package creates it) and **set it as the company’s default *Sales Tax***. *(To pin a specific tax just for cars instead, your IT team can do that in one setting — see Appendix A.)*

✅ **Checkpoint:** after you create a car and click **Generate / Update Product** (Section 4.5), open the generated product and confirm it shows the **THB price** and **7% VAT**. Then run one full test booking through to a paid deposit (Section 8) and confirm the **deposit invoice is created and marked paid** — this proves the accounting setup is correct.

---

## 4. STEP 2 — Build your catalog (in this order)

All of the below is under **Car Booking ▸ Master Data**. Follow the order — each step builds on the previous one.

### 4.1 Brands — *Master Data ▸ Car Brands*
The manufacturer (e.g. Hongqi) and the home page “Brand Heritage” section.
- **Name**, **Sequence** (display order), **Brand Logo**, **Website Description**.
- **Featured Brand** — tick this on the brand you want shown in the Heritage section.
- **Heritage** fields: Tagline, Heritage Title, Heritage Image, a button (label + link), and a “Heritage Story” rich‑text block.

### 4.2 Showrooms — *Master Data ▸ Car Dealers*
The physical locations shown in the home “Dealer Locator” and on car pages.
- **General:** Sequence, Phone, Email, **Published**, **Brands Available**, full Address, and optional **Latitude / Longitude** (used for the “Get directions” map link — if left blank the address text is used).
- **Details:** Showroom Image, Opening Hours, Website Description.
- 🔎 A showroom only appears on the site when **Published** is ticked.

### 4.3 Car Models — *Master Data ▸ Car Models* ★ the heart of the catalog
One record per car. You first see image tiles (kanban); open one to edit. The form has these tabs:

| Tab | What you set here |
|---|---|
| **General** | Display order, **Body Type** (Sedan/SUV/Coupe… — drives the “Browse by type” tiles), Seats, **Published on Website**, **Featured on Home** (show this car in the home hero), **Base Price** (the “from” price), **Deposit Amount** (what the customer pays to book), **Arrival Date** (drives “Latest Arrivals” and a *New* badge), Description, and Highlight Features (one per line). |
| **Performance** | Range (km), 0–100 km/h time, Top Speed. |
| **Media** | **Main Image** (used on cards, the hero and the product), an optional **Hero Video** (upload a file *or* paste a YouTube/Vimeo link), and the **Gallery** images. |
| **Trims** | The versions of this car and their prices (Section 4.4). |
| **Options & Pricing** | The extra price for each colour, interior, wheel and add‑on (Section 4.5). |
| **Specifications** | The spec sheet — label / value / unit, with a “Hero Highlight” tick for the key ones (Section 4.6). |
| **Home Showcase** | The rich visual home sections for this car (Section 4.7). |
| **Stories** | News/editorial pieces tied to this car (Section 4.8). |

- 🔎 A car appears in the catalog and line‑up only when **Published on Website** is ticked.
- A **Generate / Update Product** button sits at the top of the form — covered next.

### 4.4 Trims — *inside the car’s “Trims” tab (or Master Data ▸ Car Variants)*
The versions of a model (e.g. Standard / Long Range / Performance).
- **Name**, **Price**, **Available Units**, Estimated Delivery (days), **Published**.
- Exterior/Interior colour names, a colour swatch (hex), wheel type, and optional per‑trim Range / Acceleration / Top Speed (leave blank to use the model’s values).

### 4.5 Options, pricing & “Generate Product” *(turns a car into something sellable)*
A car becomes orderable only after you generate its product.

1. In the car’s **Options & Pricing** tab, set the **extra price** for each option a buyer can choose — exterior colours, interior, wheels and add‑ons.
2. Click **Generate / Update Product** at the top of the car form. This creates the sellable product: it carries the car’s name, image, **base price**, **7% VAT**, the trims (from Section 4.4) and the priced options.
3. **Whenever you change trims, options or prices, click that button again** to refresh the product.

The buyer’s configurator offers five choices: **Trim, Exterior Colour, Interior, Wheels, and Add‑ons** (add‑ons allow multiple selections). The trim is the main version; the others adjust the price.

### 4.6 Specifications — *the car’s “Specifications” tab*
The flexible spec sheet shown on the car page and home section.
- Each line: **Label** (e.g. “Range (WLTP)”), **Value** (e.g. “548”), **Unit** (e.g. “km”), and a **Hero Highlight** tick to feature the most important ones.

### 4.7 Home Showcase — *the car’s “Home Showcase” tab*
This is the campaign‑style visual content for the home page. There are five groups; fill the ones you want to use:

| Group | Where it appears on the home page |
|---|---|
| **Model Stage** | Full‑width image slider at the top (up to 3 slides) — caption, subtitle, image. |
| **Colour Studio** | Exterior colour switcher — colour name, swatch colour, image. |
| **Interior Themes** | Interior colour options — theme name, swatch, image. |
| **Highlights** | A grid of feature cards — title, subtitle, image. |
| **Cabin Story** | A wide interior “story” band — headline, subtitle, image. |

### 4.8 Stories — *the car’s “Stories” tab (or Master Data ▸ Stories)*
News/editorial articles shown on the home “Latest Stories” section and the Stories page.
- **Headline**, **Subtitle**, **Location** (dateline), optional **Car Model** (leave blank for brand‑wide), **Publish Date**, **Image**, **Excerpt**, **Body**, and a button (label + link).

### 4.9 Offers & Stats — *Master Data ▸ Offers & Promotions / Stats*
- **Offers:** promotional cards with a headline, image, badge, optional linked car, and a **start/end date** (the offer goes live and expires automatically).
- **Stats:** the big numbers in the home “stats strip”. Each is either a number you type, or a **live count** (published models, showrooms, brands, bookings, or maximum range). Add a label and an icon.

---

## 5. STEP 3 — Arrange the home page

The home page is assembled from **sections** you can switch on/off and reorder. Go to **Master Data ▸ Home Layout**.

- Each section has a **Section Type**, an optional **Car Model** (leave blank to use the car you marked **Featured on Home**), a **Sequence** (the order it appears), and an **Active** switch.
- A standard layout is pre‑loaded. Some sections are on by default; others are off and you can enable them.

**Section types you can use:**

| Section | Shows |
|---|---|
| Featured Hero | Big hero banner for the featured car |
| Model Stage | Full‑width image slider |
| Colour Studio | Exterior/interior colour switcher |
| Brand Heritage | The featured brand’s heritage block |
| Model Gallery | A photo slider |
| Model Specifications | The featured car’s key specs |
| Highlights | Feature cards |
| Cabin Story | Wide interior band |
| Model Line‑up | All published cars |
| Browse Tiles | Browse by body type / price |
| Stats Strip | The big numbers |
| Latest Arrivals | Recently arrived cars |
| Offers & Promotions | Live promotional cards |
| Latest Stories | Recent news/editorial |
| Finance Calculator | Monthly‑payment estimator |
| Dealer Locator | Showroom list |

**Which car is “featured”?** Sections that show a single car use the car you tick **Featured on Home**. If you don’t tick any, the system simply uses the first published car. *(Remember: if there are no published cars at all, these sections will be empty — see Section 2.)*

---

## 6. STEP 4 — Website settings

### 6.1 Header — *automatic, nothing to do*
The site already shows the branded header (centred logo, a minimal menu, the sign‑in/account area, and an EN/ไทย language switch). It intentionally hides the standard shop clutter (cart, search, etc.).

### 6.2 Footer — *add your real social links*
The branded footer (logos, the Hongqi Thailand address, social icons and copyright) is already in place. **Enter your real Facebook / Instagram / YouTube addresses** under *Website ▸ Configuration ▸ Settings ▸ Social Media*.

### 6.3 Set the home page
The rich “showroom” page is **not** automatically set as your site’s home page — you set it once:
- Go to *Website ▸ Site ▸ Pages*, open the **Showroom** page (its address is `/showroom`), and turn on **“Is Homepage.”**
- After this, visiting the site’s root address shows your showroom. *(Tip: while configuring, you can always preview it directly at `…/showroom`.)*

### 6.4 Turn on the Thai language
The Thai translation is included, but Thai must be **activated** for the EN/ไทย switch to appear:
- *Settings ▸ Translations ▸ Languages ▸ Add a Language* → choose **ไทย (Thai)**.
- The language switch only shows when more than one language is active.

### 6.5 Publishing
Most content is **Published** by default, so new cars, showrooms, offers, etc. appear immediately. Untick **Published** on any record you want to hide from the website.

---

## 7. STEP 5 — Online payment (the deposit)

**How the deposit works**
- The amount comes from each car’s **Deposit Amount** (Section 4.3). The customer pays **only the deposit**, never the full car price, at booking.
- When the deposit is paid, the system automatically confirms the sales order, issues a **deposit invoice**, records the **payment**, and sends the customer a confirmation SMS.

**Test mode vs. real payments**
- **Testing/training:** use the built‑in **Demo** payment method (no real money moves). This is what shows on a fresh install.
- **Going live with real Thai Baht payments:** the **2C2P** payment gateway is a **separate add‑on that must be installed and configured by your IT team**, then enabled as a payment provider with your 2C2P merchant credentials (in *Test* for sandbox, *Enabled* for production).
  > ⚠️ Important: the words “**Secure Deposit · 2C2P**” on the payment page are just a **label**. Real 2C2P payments only work once that add‑on is installed and the provider is configured. Until then, payments run through the Demo method.

---

## 8. The customer experience (what your buyer sees)

| Step | Page | What happens |
|---|---|---|
| Browse | Cars / car detail / Compare / Stories | Customer explores models, compares up to 4, reads stories. |
| 1. Configure | “Book” page | Chooses trim, colour, interior, wheels, add‑ons (price updates live), picks a showroom, enters their phone, and **ticks the privacy consent (PDPA)**. |
| 2. Verify | Verify page | Enters the **6‑digit code** sent to their phone by SMS (valid 5 minutes). |
| 3. Details | Details page | Enters name (required), email, ID/NRC, address. |
| 4. Deposit | Payment page | Pays the deposit through the online payment form. |
| 5. Done | Confirmation page | Sees the booking reference, their car, the showroom, the order and the deposit invoice, plus a “View in My Account” link. |

**Phone verification & privacy.** The customer must accept the **privacy consent (PDPA)** *before* any SMS is sent — no consent, no message. The verification code is sent only to their phone and is never shown on screen. Wrong codes are limited, and the code expires after 5 minutes.

---

## 9. Managing bookings (back office) — *Car Booking ▸ Bookings*

Each booking moves through clear statuses:

**Draft → OTP Pending → Phone Verified → Awaiting Deposit → Confirmed → In Production → Ready for Delivery → Delivered** (plus **Expired** and **Cancelled**).

The website moves a booking up to **Confirmed** automatically when the deposit is paid. Your staff then use the buttons on the booking form:
- **Confirm** — if a deposit was taken outside the website (the deposit must be fully paid).
- **Start Production** → **Ready for Delivery** → **Mark Delivered** — to progress the order.
- **Cancel** — allowed only if no successful payment exists.
- **Set to Draft** — to reopen a cancelled/expired booking.

**Abandoned bookings clean themselves up.** Unpaid bookings that sit untouched for about a day are automatically marked **Expired**, and their draft sales order is cancelled — keeping your pipeline tidy. (Timing is adjustable — see Appendix A.)

---

## 10. Customer self‑service (*My Account*)

A logged‑in customer sees, under **My Account ▸ Bookings**:
- A list of their bookings with reference, car, showroom, deposit and a **status badge**.
- A booking detail page with a **status timeline** (Verified → Deposit → Confirmed → Production → Ready → Delivered), their configured car, any **deposit invoices**, **payments**, the order total, and a **Pay Deposit** button if the deposit is still due.

Customers can only ever see **their own** bookings.

---

## 11. Who can do what (roles & access)

| Who | What they can do |
|---|---|
| **Website visitors (public)** | Browse the catalog and start a booking. |
| **Customers (logged in)** | See and track only their own bookings (read‑only). |
| **Internal staff** | View and manage bookings (no deleting). |
| **Car Booking Manager / Administrator** | Full control of catalog and bookings, including deletion and the delivery workflow. |

Assign the **Car Booking Manager** role to your dealership back‑office users; administrators have it automatically.

---

## 12. Go‑live checklist

- [ ] Company currency = **THB**; website assigned to the Thailand company *(Section 3)*
- [ ] **7% VAT** exists and is the default sales tax *(Section 3)*
- [ ] Brands added (with Heritage) *(4.1)*
- [ ] Showrooms added, **Published**, with map coordinates *(4.2)*
- [ ] Car Models complete — General, Performance, Media, Specs, Showcase, Stories *(4.3, 4.6–4.8)*
- [ ] Trims and **Options & Pricing** set, then **Generate Product** clicked *(4.4–4.5)*
- [ ] Generated products show **THB price + 7% VAT** *(Section 3 checkpoint)*
- [ ] Home Layout sections enabled/ordered; a car marked **Featured on Home** *(Section 5)*
- [ ] Footer **social links** entered *(6.2)*
- [ ] **Showroom set as the home page** *(6.3)*
- [ ] **Thai language activated** *(6.4)*
- [ ] Payment ready — Demo for testing, **2C2P installed & configured** for live THB *(Section 7)*
- [ ] Full test booking completed: configure → verify → details → deposit → confirmation → My Account *(Sections 8–10)*
- [ ] (Live site) at least one car **published**, or sample content loaded, so the home page isn’t empty *(Section 2)*

---

## Appendix A — Advanced settings *(for your IT/technical team)*

A few behaviours are controlled by internal settings (*Settings ▸ Technical ▸ System Parameters*). Functional users normally don’t touch these — share this table with IT if you need to change a default.

| Setting controls… | Default | Notes |
|---|---|---|
| The specific VAT tax applied to cars | (uses company default) | Set only if you want a tax different from the company default. |
| “New Arrival” badge duration | 60 days | How long after the arrival date a car shows as *New*. |
| When unpaid bookings expire | 24 hours | Idle, unpaid bookings auto‑expire after this. |
| SMS code resend wait time | 30 seconds | Minimum gap before a customer can resend the code. |
| Max verification codes per phone, per hour | 5 | Protects against SMS abuse/cost. |
| Deposit invoice automation | On | Deposit invoices are issued and reconciled automatically on payment. |

SMS is sent through Odoo’s built‑in SMS service (requires SMS credits or a configured SMS provider).

---

*Car Dealer Website · Hongqi Thailand · built on Odoo 19 · Basic Solution Co., Ltd.*
