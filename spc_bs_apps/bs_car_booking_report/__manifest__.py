# -*- coding: utf-8 -*-
{
    'name': 'BS Car Booking Report – Individual Contract',
    'summary': 'QWeb PDF report: Standard car booking contract (individual/personal)',
    'category': 'Website/Booking',
    'version': '19.0.1.1.0',
    'author': 'Basic Solution Co., Ltd.',
    'license': 'LGPL-3',
    'depends': ['bs_car_booking'],
    # No new models — report module only.
    'data': [
        'report/report_individual_setup.xml',
        'report/report_template.xml',
        'report/report_individual_header.xml',
        'report/report_individual_footer.xml',
        'report/report_individual_content.xml',
        'views/booking_report_views.xml',
    ],
    'installable': True,
    'auto_install': False,
}
