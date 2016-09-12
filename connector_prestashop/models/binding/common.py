# -*- coding: utf-8 -*-
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from openerp import models, fields, api
from openerp.addons.connector.session import ConnectorSession
from ...unit.importer import import_record


class PrestashopBinding(models.AbstractModel):
    _name = 'prestashop.binding'
    _inherit = 'external.binding'
    _description = 'PrestaShop Binding (abstract)'

    # 'openerp_id': openerp-side id must be declared in concrete model
    backend_id = fields.Many2one(
        comodel_name='prestashop.backend',
        string='PrestaShop Backend',
        required=True,
        ondelete='restrict'
    )
    # TODO : do I keep the char like in Magento, or do I put a PrestaShop ?
    prestashop_id = fields.Integer('ID on PrestaShop')

    _sql_constraints = [
        ('prestashop_uniq', 'unique(backend_id, prestashop_id)',
         'A record with same ID on PrestaShop already exists.'),
    ]

    @api.multi
    def resync(self):
        session = ConnectorSession.from_env(self.env)
        func = import_record
        if self.env.context.get('connector_delay'):
            func = import_record.delay
        for record in self:
            func(session, self._name, record.backend_id.id,
                 record.prestashop_id)
        return True