# -*- coding: utf-8 -*-
# Part of Basic Solution Co., Ltd.

{
    'name': 'BS Car Booking',
    'summary': 'Premium car booking & reservation system with OTP verification and deposit',
    'description': """
BS Car Booking - Premium Automotive Booking System
===================================================

A premium automotive dealer booking website module featuring:

* Car brands, models & variants management
* Dealer/showroom network
* Online booking with real-time configuration pricing
* Deposit collection via payment gateway
* SMS OTP verification for customer phone
* Premium responsive showroom templates
* Backend dashboard for booking management
* Automated SMS/email notifications

Website Journey:
1. Browse car models with premium gallery
2. Select car variant (color, trim, options)
3. Choose preferred dealer
4. Enter personal info + phone OTP verification
5. Pay deposit online
6. Receive booking confirmation via SMS
""",
    'category': 'Website/Booking',
    'version': '19.0.4.2.1',
    'author': 'Basic Solution Co., Ltd.',
    'maintainer': 'Basic Solution Co., Ltd.',
    'website': 'https://basicsolution.com/',
    'license': 'LGPL-3',
    'sequence': 100,
    'depends': [
        'base',
        'website',
        'website_sale',
        'sale_management',
        'account_payment',
        'payment',
        'payment_demo',
        'crm',
        'sms',
        'mail',
        'contacts',
    ],
    'data': [
        # Security
        'security/booking_groups.xml',
        'security/ir.model.access.csv',
        'security/booking_security.xml',

        # Data
        'data/booking_sequence_data.xml',
        'data/booking_cron_data.xml',
        'data/product_attribute_data.xml',
        'data/home_layout_data.xml',

        # Views - Backend
        'views/bs_car_brand_views.xml',
        'views/bs_car_model_views.xml',
        'views/bs_car_variant_views.xml',
        'views/bs_car_dealer_views.xml',
        'views/bs_car_booking_views.xml',
        'views/crm_lead_views.xml',
        'views/menu_views.xml',
        'views/bs_car_offer_views.xml',
        'views/bs_car_stat_views.xml',
        'views/bs_car_home_block_views.xml',
        'views/bs_car_showcase_views.xml',

        # Views - Website
        'views/website_header.xml',
        'views/website_footer.xml',
        'views/website_templates.xml',
        'views/website_compare_templates.xml',
        'views/website_booking_templates.xml',
        'views/website_confirmation_templates.xml',
        'views/portal_templates.xml',
        'views/story_templates.xml',
        'views/snippets.xml',
        'views/showroom_home.xml',
        'views/privacy_page.xml',

        # Website navigation menu
        'data/website_menu_data.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'bs_car_booking/static/src/scss/theme.scss',
            'bs_car_booking/static/src/js/interactions/booking_form.js',
            'bs_car_booking/static/src/js/interactions/customer_info.js',
            'bs_car_booking/static/src/js/interactions/finance_calc.js',
            'bs_car_booking/static/src/js/interactions/gallery_lightbox.js',
            'bs_car_booking/static/src/js/interactions/home_showcase.js',
            'bs_car_booking/static/src/js/interactions/otp_verification.js',
            'bs_car_booking/static/src/js/interactions/showroom_motion.js',
        ],
    },
    'demo': [
        'demo/car_demo.xml',
    ],
    'images': [
        'static/description/cover.png',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'post_init_hook': 'post_init_hook',
}
