# -*- coding: utf-8 -*-
# Part of Basic Solution Co., Ltd.

{
    'name': 'BS Car Booking Demo Data',
    'summary': 'Marketing-only Hongqi demo data for BS Car Booking',
    'category': 'Website/Booking',
    'version': '19.0.1.0.0',
    'author': 'Basic Solution Co., Ltd.',
    'maintainer': 'Basic Solution Co., Ltd.',
    'website': 'https://basicsolution.com/',
    'license': 'LGPL-3',
    'depends': [
        'bs_car_booking',
        'theme_bs_hongqi_car',
    ],
    'data': [
        'data/product_option_values.xml',
        'data/hongqi_marketing_data.xml',
        'data/hongqi_website_sections.xml',
        'data/hongqi_home_layout.xml',
        'data/hongqi_demo_scope.xml',
        'data/hongqi_model_options.xml',
        'data/hongqi_generate_products.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
