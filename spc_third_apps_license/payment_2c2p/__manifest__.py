# -*- coding: utf-8 -*-
#################################################################################
# Author      : Webkul Software Pvt. Ltd. (<https://webkul.com/>)
# Copyright(c): 2015-Present Webkul Software Pvt. Ltd.
# All Rights Reserved.
#
#
#
# This program is copyright property of the author mentioned above.
# You can`t redistribute it and/or modify it.
#
#
# You should have received a copy of the License along with this program.
# If not, see <https://store.webkul.com/license.html/>
#################################################################################
{
    "name":  "2c2p Payment Acquirer",
    "summary":  """The module allow the customers to make payments on Odoo website using 2c2p Payment Gateway. The module facilitates 2c2p integration with Odoo""",
    "category":  "Website",
    "version":  "1.0.0",
    "sequence":  1,
    "author":  "Webkul Software Pvt. Ltd.",
    "license":  "Other proprietary",
    "website":  "https://store.webkul.com/Odoo-2c2p-Payment-Acquirer.html",
    "live_test_url":  'https://odoodemo.webkul.in/?module=payment_2c2p',
    "description":  """Odoo Website 2c2p Payment Acquirer
Odoo 2c2p Payment Gateway
Payment Gateway
2c2p
2c2p
2c2p integration
Payment acquirer
Payment processing
Payment processor
Website payments
Sale orders payment
Customer payment
Integrate 2c2p payment acquirer in Odoo
Integrate 2c2p payment gateway in Odoo""",
    "depends":  ['payment'],
    "data":  [
        'views/payment_views.xml',
        'views/payment_2c2p_templates.xml',
        'data/payment_acquirer_data.xml',
    ],
    "images":  ['static/description/banner.png'],
    "application":  True,
    "installable":  True,
    "auto_install":  False,
    "price":  69,
    "currency":  "USD",
    "uninstall_hook":  "uninstall_hook",
    "pre_init_hook":  "pre_init_check",
    'post_init_hook':  'post_init_hook',
}
