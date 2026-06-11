{
    'name': 'BS Test Drive API Config',
    'summary': 'ReadyPlanet R-CRM API configuration and submission logging for Test Drive requests',
    'version': '19.0.1.0.0',
    'category': 'Website',
    'author': 'Basic Solution Co., Ltd.',
    'maintainer': 'Basic Solution Co., Ltd.',
    'website': 'https://basicsolution.com/',
    'license': 'LGPL-3',
    'depends': ['base', 'website'],
    'data': [
        'security/bs_api_testdrive_groups.xml',
        'security/ir.model.access.csv',
        'views/bs_api_testdrive_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
