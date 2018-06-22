# -*- coding: utf-8 -*-
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

import re
import logging

from openerp import fields
from openerp.addons.connector.queue.job import job
from openerp.addons.connector.unit.mapper import (
    ImportMapper,
    mapping,
    only_create,
)
from ...unit.importer import (
    PrestashopImporter,
    import_batch,
    DelayedBatchImporter,
)
from ...backend import prestashop
from ...unit.mapper import backend_to_m2o
from ...connector import add_checkpoint

_logger = logging.getLogger(__name__)

@prestashop
class PartnerImportMapper(ImportMapper):
    _model_name = 'prestashop.res.partner'

    direct = [
        ('date_add', 'date_add'),
        ('date_upd', 'date_upd'),
        ('email', 'email'),
        ('newsletter', 'newsletter'),
        ('company', 'company'),
        ('active', 'active'),
        ('note', 'comment'),
        (backend_to_m2o('id_shop_group'), 'shop_group_id'),
        (backend_to_m2o('id_shop'), 'shop_id'),
        (backend_to_m2o('id_default_group'), 'default_category_id'),
    ]

    @only_create
    @mapping
    def openerp_id(self, record):
        """ Will bind the product to an existing one with the same code """
        if self.backend_record.matching_customer:
            code = record.get(self.backend_record.matching_customer_ch.value)
            
            if code:
                partner = self.env['res.partner'].search(
                [('ref', '=', code)], limit=1)
                if partner:
                    return {'openerp_id': partner.id}
        else:
            return


    @mapping
    def pricelist(self, record):
        binder = self.binder_for('prestashop.groups.pricelist')
        pricelist = binder.to_openerp(record['id_default_group'], unwrap=True)
        if not pricelist:
            return {}
        return {'property_product_pricelist': pricelist.id}

    @mapping
    def birthday(self, record):
        if record['birthday'] in ['0000-00-00', '']:
            return {}
        return {'birthday': record['birthday']}

    @mapping
    def name(self, record):
        parts = [record['firstname'], record['lastname']]
        name = ' '.join(p.strip() for p in parts if p.strip())
        return {'name': name}

    @mapping
    def groups(self, record):
        groups = record.get(
            'associations', {}).get('groups', {}).get(
            self.backend_record.get_version_ps_key('group'), [])
        if not isinstance(groups, list):
            groups = [groups]
        model_name = 'prestashop.res.partner.category'
        partner_category_bindings = self.env[model_name].browse()
        binder = self.binder_for(model_name)
        for group in groups:
            partner_category_bindings |= binder.to_openerp(group['id'])

        result = {'group_ids': [(6, 0, partner_category_bindings.ids)],
                  'category_id': [(4, b.openerp_id.id)
                                  for b in partner_category_bindings]}
        return result

    @mapping
    def backend_id(self, record):
        return {'backend_id': self.backend_record.id}

    @mapping
    def lang(self, record):
        binder = self.binder_for('prestashop.res.lang')
        erp_lang = None
        if record.get('id_lang'):
            erp_lang = binder.to_openerp(record['id_lang'])
        if not erp_lang:
            erp_lang = self.env.ref('base.lang_en')
        return {'lang': erp_lang.code}

    @mapping
    def customer(self, record):
        return {'customer': True}

    @mapping
    def company_id(self, record):
        return {'company_id': self.backend_record.company_id.id}


@prestashop
class ResPartnerImporter(PrestashopImporter):
    _model_name = 'prestashop.res.partner'

    def _import_dependencies(self):
        groups = self.prestashop_record.get('associations', {}) \
            .get('groups', {}).get(
            self.backend_record.get_version_ps_key('group'), [])
        if not isinstance(groups, list):
            groups = [groups]
        for group in groups:
            self._import_dependency(group['id'],
                                    'prestashop.res.partner.category')

    def _after_import(self, binding):
        super(ResPartnerImporter, self)._after_import(binding)
        binder = self.binder_for()
        ps_id = binder.to_backend(binding)
        import_batch.delay(
            self.session,
            'prestashop.address',
            self.backend_record.id,
            filters={'filter[id_customer]': '%d' % (ps_id,)},
            priority=10,
        )


@prestashop
class PartnerBatchImporter(DelayedBatchImporter):
    _model_name = 'prestashop.res.partner'


@prestashop
class AddressImportMapper(ImportMapper):
    _model_name = 'prestashop.address'

    direct = [
        ('address1', 'street'),
        ('address2', 'street2'),
        ('city', 'city'),
        ('other', 'comment'),
        ('phone', 'phone'),
        ('phone_mobile', 'mobile'),
        ('postcode', 'zip'),
        ('date_add', 'date_add'),
        ('date_upd', 'date_upd'),
        (backend_to_m2o('id_customer'), 'prestashop_partner_id'),
    ]
    
    @only_create
    @mapping
    def openerp_id(self, record):
        """ Will bind the product to an existing one with the same code """
        if self.backend_record.matching_customer:
            code = self.parent_id(record)['parent_id']
            to_match = self.name(record)['name']
            if code and to_match:
                address = self.env['res.partner'].search(
                [('name', '=', to_match),('parent_id','=',code)], limit=1)
                if address:
                    return {'openerp_id': address.id}
        else:
            return {}


    

    @mapping
    def backend_id(self, record):
        return {'backend_id': self.backend_record.id}

    @mapping
    def parent_id(self, record):
        binder = self.binder_for('prestashop.res.partner')
        parent = binder.to_openerp(record['id_customer'], unwrap=True)
        vals = {'parent_id': parent.id}
        if parent and not parent.phone and 'phone' in record:
            parent.phone = record['phone']
        if parent and parent.email and not 'email' in record:
            vals.update({'email': parent.email})
        return vals

    @mapping
    def name(self, record):
        _logger.debug('RECorD FOR NAME and company %s' % record)
        parts = [record['firstname'], record['lastname']]
        
        if record['company']:
            parts.append('(%s)' % record['company'])
        name = ' '.join(p.strip() for p in parts if p.strip())
        return {'name': name}

    @mapping
    def customer(self, record):
        return {'customer': True}

    @mapping
    def country(self, record):
        if record.get('id_country'):
            binder = self.binder_for('prestashop.res.country')
            country = binder.to_openerp(record['id_country'], unwrap=True)
            return {'country_id': country.id}
        return {}

    @mapping
    def company_id(self, record):
        return {'company_id': self.backend_record.company_id.id}

    @only_create
    @mapping
    def type(self, record):
        # do not set 'contact', otherwise the address fields are shared with
        # the parent
        return {'type': 'other'}


@prestashop
class AddressImporter(PrestashopImporter):
    _model_name = 'prestashop.address'

    def _check_vat(self, vat):
        vat_country, vat_number = vat[:2].lower(), vat[2:]
        partner_model = self.env['res.partner']
        return partner_model.simple_vat_check(vat_country, vat_number)

    def _after_import(self, binding):
        record = self.prestashop_record
        vat_number = None
        if record['vat_number']:
            vat_number = record['vat_number'].replace('.', '').replace(' ', '')
        # TODO move to custom localization module
        elif not record['vat_number'] and record.get('dni'):
            vat_number = record['dni'].replace('.', '').replace(
                ' ', '').replace('-', '')
        if vat_number:
            # TODO: move to custom module
            regexp = re.compile('^[a-zA-Z]{2}')
            if not regexp.match(vat_number):
                vat_number = 'ES' + vat_number
            if self._check_vat(vat_number):
                binding.parent_id.write({'vat': vat_number})
            else:
                add_checkpoint(
                    self.session,
                    'res.partner',
                    binding.parent_id.id,
                    self.backend_record.id
                )


@prestashop
class AddressBatchImporter(DelayedBatchImporter):
    _model_name = 'prestashop.address'


@job(default_channel='root.prestashop')
def import_customers_since(session, backend_id, since_date=None):
    """ Prepare the import of partners modified on PrestaShop """
    filters = None
    if since_date:
        filters = {
            'date': '1',
            'filter[date_upd]': '>[%s]' % (since_date)}
    now_fmt = fields.Datetime.now()
    import_batch(
        session, 'prestashop.res.partner.category', backend_id, filters
    )
    import_batch(
        session, 'prestashop.res.partner', backend_id, filters, priority=15
    )

    session.env['prestashop.backend'].browse(backend_id).write({
        'import_partners_since': now_fmt,
    })
