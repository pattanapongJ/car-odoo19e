# -*- coding: utf-8 -*-
# Part of Basic Solution Co., Ltd.

{
    'name': 'Hongqi Car Website Theme',
    'summary': 'Opt-in Hongqi brand website theme for BS Car Booking',
    'category': 'Theme',
    'version': '19.0.1.0.0',
    'author': 'Basic Solution Co., Ltd.',
    'maintainer': 'Basic Solution Co., Ltd.',
    'website': 'https://basicsolution.com/',
    'license': 'LGPL-3',
    'depends': [
        'website',
        'html_builder',
        'website_crm',
        'portal',
        'bs_car_booking',
    ],
    'data': [
        'data/theme_assets.xml',
        'data/theme_layout.xml',
        'data/theme_cleanup.xml',
        'data/theme_pages_menus.xml',
    ],
    'images': [
        'static/description/cover.png',
        'static/description/theme_bs_hongqi_car_screenshot.jpg',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
