# -*- coding: utf-8 -*-
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import datetime
import logging

from odoo import fields, _

from odoo.addons.component.core import Component
from odoo.addons.connector.components.mapper import mapping, external_to_m2o

_logger = logging.getLogger(__name__)
try:
    from prestapyt import PrestaShopWebServiceError
except:
    _logger.debug('Cannot import from `prestapyt`')


class ProductProductExportMapper(Component):
    _name = 'prestashop.product.combination.export.mapper'
    _inherit = 'translation.prestashop.export.mapper'
    _apply_on = 'prestashop.product.combination'

    _model_name = 'prestashop.product.combination'

    _translatable_fields = [
    ]

    def _export_images(self):
        if self.binding.image_ids:
            image_binder = self.binder_for('prestashop.product.image')
            for image_line in self.binding.image_ids:
                image_ext_id = image_binder.to_backend(
                    image_line.id, wrap=True)
                if not image_ext_id:
                    image_ext_id = \
                        self.session.env['prestashop.product.image']\
                            .with_context(connector_no_export=True).create({
                                'backend_id': self.backend_record.id,
                                'odoo_id': image_line.id,
                            }).id
                    image_content = getattr(image_line, "_get_image_from_%s" %
                                            image_line.storage)()
                    export_record(
                        self.session,
                        'prestashop.product.image',
                        image_ext_id,
                        image_content)

    def _export_dependencies(self):
        """ Export the dependencies for the product"""
        # TODO add export of category
        attribute_binder = self.binder_for(
            'prestashop.product.combination.option')
        option_binder = self.binder_for(
            'prestashop.product.combination.option.value')
        Option = self.env['prestashop.product.combination.option']
        OptionValue = self.env['prestashop.product.combination.option.value']
        for value in self.binding.attribute_value_ids:
            prestashop_option_id = attribute_binder.to_backend(
                value.attribute_id.id, wrap=True)
            if not prestashop_option_id:
                option_binding = Option.search(
                    [('backend_id', '=',  self.backend_record.id),
                     ('odoo_id', '=', value.attribute_id.id)])
                if not option_binding:
                    option_binding = Option.with_context(
                        connector_no_export=True).create({
                            'backend_id': self.backend_record.id,
                            'odoo_id': value.attribute_id.id})
                export_record(self.session,
                              'prestashop.product.combination.option',
                              option_binding.id)
            prestashop_value_id = option_binder.to_backend(
                value.id, wrap=True)
            if not prestashop_value_id:
                value_binding = OptionValue.search(
                    [('backend_id', '=',  self.backend_record.id),
                     ('odoo_id', '=', value.id)]
                )
                if not value_binding:
                    option_binding = Option.search(
                        [('backend_id', '=',  self.backend_record.id),
                         ('odoo_id', '=', value.attribute_id.id)])
                    value_binding = OptionValue.with_context(
                        connector_no_export=True).create({
                            'backend_id': self.backend_record.id,
                            'odoo_id': value.id,
                            'id_attribute_group': option_binding.id})
                export_record(
                    self.session,
                    'prestashop.product.combination.option.value',
                    value_binding.id)
        # self._export_images()

    def update_quantities(self):
        self.binding.odoo_id.with_context(
            self.session.context).update_prestashop_qty()

    def _after_export(self):
        self.update_quantities()


@prestashop
class ProductCombinationExportMapper(TranslationPrestashopExportMapper):
    _model_name = 'prestashop.product.combination'

    direct = [
        ('weight', 'weight'),
    ]

    @mapping
    def ean13(self, record):
        if record.barcode:
            return {'ean13': record.barcode}

    @mapping
    def wholesale_price(self, record):
        return {'wholesale_price': record.standard_price or 0.00}

    def _get_factor_tax(self, tax):
        return (1 + tax.amount / 100) if tax.price_include else 1.0

    @mapping
    def list_price(self, record):
        tax = record.taxes_id
        if tax.price_include and tax.amount_type == 'percent':
            # 6 is the rounding precision used by PrestaShop for the
            # tax excluded price.  we can get back a 2 digits tax included
            # price from the 6 digits rounded value
            return {
                'price': str(
                    round(record.lst_price / self._get_factor_tax(tax), 6))
            }
        else:
            return {'price': str(record.lst_price)}

    @mapping
    def attribute_price(self, record):
        tax = record.taxes_id
        if tax.price_include and tax.amount_type == 'percent':
            # 6 is the rounding precision used by PrestaShop for the
            # tax excluded price.  we can get back a 2 digits tax included
            # price from the 6 digits rounded value
            return {
                'attribute_price': str(
                    round(record.lst_price / self._get_factor_tax(tax), 6)),
                'price': str(
                    round(record.lst_price / self._get_factor_tax(tax), 6))
            }
        else:
            return {
                'attribute_price': str(record.lst_price),
                'price': str(record.lst_price)
            }

    @mapping
    def reference(self, record):
        if record.default_code:
            return {'reference': record.default_code[0:32]}

    @mapping
    def name(self, record):
        value = {'language': []}
        records_by_lang = self._get_record_by_lang(record)
        for language_id, trans_record in records_by_lang.items():
            value['language'].append({
                'attrs': {'id': str(language_id)},
                'value': trans_record.name,
            })
        return {'name': value}

    @mapping
    def id_product(self, record):
        if not record.product_tmpl_id:
            return
        product_binder = self.binder_for('prestashop.product.template')
        ext_product_id = product_binder.to_external(
            record.product_tmpl_id.id, wrap=True
        )
        return {
            'id_product': ext_product_id,
        }

    @mapping
    def associations(self, record):
        associations = OrderedDict([
            ('product_option_values',
                {'product_option_value':
                 self._get_product_option_value(record)}),
        ])
        image = self._get_combination_image(record)
        if image:
            associations['images'] = {
                'image': self._get_combination_image(record)
            }
        return {'associations': associations}

        option_value = []
        option_name = []
        attr_values_binder = self.binder_for('prestashop.product.combination.option.value')
        for attr in record.attribute_value_ids:
            value_id = attr_values_binder.to_external(
                attr.id, wrap=True
            )
            if value_id:
                option_value.append({'id': value_id})
                option_name.append(attr.name)

        return {
            'associations': {
                'product_option_values': {
                    'product_option_value': option_value,
                }
            },
            'reference': record.default_code or ' '.join(x for x in option_name),
        }

    @mapping
    def minimal_quantity(self, record):
        return {'minimal_quantity': 1}

    @mapping
    def low_stock_alert(self, record):
        return {'low_stock_alert': 1}


class ProductProductExporter(Component):
    _name = 'prestashop.product.combination.exporter'
    _inherit = 'translation.prestashop.exporter'
    _apply_on = 'prestashop.product.combination'
    _model_name = 'prestashop.product.combination'

    def _export_dependencies(self):
        """ Export the simple delivery before export lines """
        record = self.binding and self.binding.odoo_id
        if record and record.product_tmpl_id:
            self._export_dependency(record.product_tmpl_id, 'prestashop.product.template')

        if record and record.attribute_value_ids:
            for attr in record.attribute_value_ids:
                self._export_dependency(attr, 'prestashop.product.combination.option.value')


class ProductAttributeMapper(Component):
    _name = 'prestashop.product.combination.option.export.mapper'
    _inherit = 'translation.prestashop.export.mapper'
    _apply_on = 'prestashop.product.combination.option'

    _model_name = 'prestashop.product.combination.option'

    _translatable_fields = [
        ('name', 'name'),
        ('name', 'public_name'),
    ]

    direct = [
        # is_color_group
        # position
    ]

    @mapping
    def group_type(self, record):
        return {'group_type': 'select'}

    @mapping
    def name(self, record):
        value = {'language': []}
        records_by_lang = self._get_record_by_lang(record)
        for language_id, trans_record in records_by_lang.items():
            value['language'].append({
                'attrs': {'id': str(language_id)},
                'value': trans_record.name,
            })
        return {'name': value}

    @mapping
    def public_name(self, record):
        value = {'language': []}
        records_by_lang = self._get_record_by_lang(record)
        for language_id, trans_record in records_by_lang.items():
            value['language'].append({
                'attrs': {'id': str(language_id)},
                'value': trans_record.name,
            })
        return {'public_name': value}

    @mapping
    def data_add(self, record):
        if record.create_date:
            return {'date_add': fields.Datetime.from_string(record.create_date).strftime('%Y-%m-%d %H:%M:%S')}
        else:
            return {'date_add': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

    @mapping
    def data_upd(self, record):
        if record.write_date:
            return {'date_upd': fields.Datetime.from_string(record.write_date).strftime('%Y-%m-%d %H:%M:%S')}
        else:
            return {'date_upd': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}


class ProductAttributeExporter(Component):
    _name = 'prestashop.product.combination.option.exporter'
    _inherit = 'translation.prestashop.exporter'
    _apply_on = 'prestashop.product.combination.option'
    _model_name = 'prestashop.product.combination.option'


class ProductAttributeValueMapper(Component):
    _name = 'prestashop.product.combination.option.value.export.mapper'
    _inherit = 'translation.prestashop.export.mapper'
    _apply_on = 'prestashop.product.combination.option.value'

    _model_name = 'prestashop.product.combination.option.value'

    _translatable_fields = [
        ('name', 'name'),
    ]

    direct = [
    ]

    @mapping
    def name(self, record):
        value = {'language': []}
        records_by_lang = self._get_record_by_lang(record)
        for language_id, trans_record in records_by_lang.items():
            value['language'].append({
                'attrs': {'id': str(language_id)},
                'value': trans_record.name,
            })
        return {'name': value}

    @mapping
    def id_attribute_group(self, record):
        if not record.attribute_id:
            return {'id_attribute_group': 2}
        category_binder = self.binder_for('prestashop.product.combination.option')
        ext_attr_id = category_binder.to_external(
            record.attribute_id.id, wrap=True
        )
        return {
            'id_attribute_group': ext_attr_id,
        }


class ProductAttributeValueExporter(Component):
    _name = 'prestashop.product.combination.option.value.exporter'
    _inherit = 'translation.prestashop.exporter'
    _apply_on = 'prestashop.product.combination.option.value'
    _model_name = 'prestashop.product.combination.option.value'

    def _export_dependencies(self):
        """ Export the simple delivery before export lines """
        record = self.binding and self.binding.odoo_id
        if record and record.attribute_id:
            self._export_dependency(record.attribute_id, 'prestashop.product.combination.option')
