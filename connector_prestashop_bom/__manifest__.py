# -*- coding: utf-8 -*-
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

{
    'name': 'Connector Prestashop BoM',
    'summary': 'Compute product qty with BoM',
    'version': '10.0.1.0.0',
    'category': 'Connector',
    'website': 'https://odoo-community.org/',
    'author': 'Kerpeo, '
              'Odoo Community Association (OCA)',
    'license': 'AGPL-3',
    'application': False,
    'installable': True,
    'depends': [
        'connector_prestashop',
        'mrp',
    ],
    'data': [
    ]
}
