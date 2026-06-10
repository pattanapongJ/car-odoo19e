# -*- coding: utf-8 -*-
{
    'name': 'BS 2C2P Payment log',
    'version': '19.0.1.0.0',
    'category': 'Payment',
    'summary': 'Logs all 2C2P payment callbacks.',
    'author': 'BS',
    'depends': ['payment_2c2p', 'account'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/payment_log_views.xml',
        'data/payment_provider_data.xml',
    ],
    'installable': True,
    'auto_install': False,
    'post_init_hook': 'post_init_hook',
}
