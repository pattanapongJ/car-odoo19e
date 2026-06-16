# -*- coding: utf-8 -*-
# Part of Basic Solution Co., Ltd.

import base64

from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestBookingValidation(TransactionCase):
    """Server-side CRUD validation for the car-booking lifecycle: field
    constraints, the state-transition guard, company/website immutability and
    the delete guard. These run even under sudo() (the website funnel path), so
    they are the real guardrail for portal-created bookings."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.brand = cls.env['bs.car.brand'].create({'name': 'Test Brand'})
        cls.model = cls.env['bs.car.model'].create({
            'name': 'Test Model',
            'brand_id': cls.brand.id,
        })

    def _new_booking(self, **vals):
        return self.env['bs.car.booking'].create({
            'customer_phone': '0812345678',
            'brand_id': self.brand.id,
            'model_id': self.model.id,
            **vals,
        })

    # --- Phone ---------------------------------------------------------------
    def test_phone_valid_formats(self):
        # Separators are stripped before the 7–15 digit check.
        for phone in ('0812345678', '+95 9 123 4567', '081-234 5678'):
            self._new_booking(customer_phone=phone)

    def test_phone_invalid_raises(self):
        for phone in ('123', 'not-a-phone', '+12345678901234567890'):
            with self.assertRaises(ValidationError):
                self._new_booking(customer_phone=phone)

    # --- Email ---------------------------------------------------------------
    def test_email_valid_accepted(self):
        booking = self._new_booking(customer_email='customer@example.com')
        self.assertEqual(booking.customer_email, 'customer@example.com')

    def test_email_invalid_raises(self):
        with self.assertRaises(ValidationError):
            self._new_booking(customer_email='not-an-email')

    # --- Monetary amounts ----------------------------------------------------
    def test_negative_deposit_raises(self):
        with self.assertRaises(ValidationError):
            self._new_booking(deposit_amount=-50)

    def test_negative_car_price_raises(self):
        booking = self._new_booking()
        with self.assertRaises(ValidationError):
            booking.car_price = -1

    # --- Rating --------------------------------------------------------------
    def test_rating_out_of_range_raises(self):
        booking = self._new_booking()
        with self.assertRaises(ValidationError):
            booking.rating = 99

    def test_rating_in_range_ok(self):
        booking = self._new_booking()
        booking.rating = 5

    # --- State-transition guard ---------------------------------------------
    def test_illegal_state_transition_raises(self):
        booking = self._new_booking()
        self.assertEqual(booking.state, 'draft')
        with self.assertRaises(ValidationError):
            booking.write({'state': 'delivered'})

    def test_legal_state_transition_ok(self):
        booking = self._new_booking()
        booking.write({'state': 'otp_pending'})
        self.assertEqual(booking.state, 'otp_pending')

    def test_bypass_context_allows_any_state(self):
        # Internal transitions go through the bypass flag.
        booking = self._new_booking()
        booking.with_context(bs_booking_bypass_state_guard=True).write({'state': 'confirmed'})
        self.assertEqual(booking.state, 'confirmed')

    # --- Company / website immutability -------------------------------------
    def test_company_change_blocked(self):
        company2 = self.env['res.company'].create({'name': 'Other Co'})
        booking = self._new_booking(company_id=self.env.company.id)
        with self.assertRaises(ValidationError):
            booking.write({'company_id': company2.id})

    def test_same_company_write_ok(self):
        booking = self._new_booking(company_id=self.env.company.id)
        # Writing the unchanged value must not trip the guard.
        booking.write({'company_id': self.env.company.id})

    # --- Delete guard --------------------------------------------------------
    def test_delete_draft_allowed(self):
        booking = self._new_booking()
        booking.unlink()
        self.assertFalse(booking.exists())

    def test_delete_confirmed_blocked(self):
        booking = self._new_booking()
        booking.with_context(bs_booking_bypass_state_guard=True).write({'state': 'confirmed'})
        with self.assertRaises(ValidationError):
            booking.unlink()

    def test_duplicate_draft_is_deletable(self):
        # Regression: a duplicate must not inherit the paid deposit (copy=False),
        # so the fresh draft copy is a clean, deletable pre-commitment record.
        booking = self._new_booking()
        booking.deposit_paid = 500
        copy = booking.copy()
        self.assertEqual(copy.state, 'draft')
        self.assertFalse(copy.deposit_paid)
        copy.unlink()
        self.assertFalse(copy.exists())

    def test_delete_cancelled_with_payment_blocked(self):
        booking = self._new_booking()
        booking.deposit_paid = 500
        booking.with_context(bs_booking_bypass_state_guard=True).write({'state': 'cancelled'})
        with self.assertRaises(ValidationError):
            booking.unlink()

    def test_duplicate_does_not_carry_private_data(self):
        # A duplicate must not inherit another customer's uploaded documents
        # (copy=False on the One2many) — privacy + legal-audit integrity.
        dtype = self.env['bs.car.document.type'].create({'name': 'ID Card'})
        booking = self._new_booking()
        self.env['bs.car.booking.document'].create({
            'booking_id': booking.id,
            'document_type_id': dtype.id,
            'attachment': base64.b64encode(b'fake'),
            'filename': 'id.pdf',
        })
        self.assertTrue(booking.document_ids)
        copy = booking.copy()
        self.assertFalse(copy.document_ids)

    def test_duplicate_logs_provenance(self):
        booking = self._new_booking()
        copy = booking.copy()
        self.assertTrue(
            any('Duplicated from' in (m.body or '') for m in copy.message_ids),
            'the duplicate should record its provenance in the chatter')

    def _booking_attachments(self, booking):
        return self.env['ir.attachment'].search([
            ('res_model', '=', 'bs.car.booking'), ('res_id', '=', booking.id)])

    def test_document_mirrors_to_booking_attachments(self):
        # An uploaded document must surface in the booking's attachment box, and
        # the mirror must be removed with the line (PDPA-safe, no orphaned PII).
        dtype = self.env['bs.car.document.type'].create({'name': 'ID Card'})
        booking = self._new_booking()
        self.assertFalse(self._booking_attachments(booking))
        doc = self.env['bs.car.booking.document'].create({
            'booking_id': booking.id,
            'document_type_id': dtype.id,
            'attachment': base64.b64encode(b'fake'),
            'filename': 'id.pdf',
        })
        self.assertTrue(doc.booking_attachment_id)
        self.assertIn(doc.booking_attachment_id, self._booking_attachments(booking))
        doc.unlink()
        self.assertFalse(self._booking_attachments(booking))


@tagged('post_install', '-at_install')
class TestCatalogValidation(TransactionCase):
    """Constraints on the catalog models that feed bookings."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.brand = cls.env['bs.car.brand'].create({'name': 'Test Brand'})
        cls.model = cls.env['bs.car.model'].create({
            'name': 'Test Model',
            'brand_id': cls.brand.id,
        })

    def test_model_negative_base_price_raises(self):
        with self.assertRaises(ValidationError):
            self.env['bs.car.model'].create({
                'name': 'Cheap', 'brand_id': self.brand.id, 'base_price': -100,
            })

    def test_model_invalid_year_raises(self):
        with self.assertRaises(ValidationError):
            self.model.model_year = '1990'

    def test_variant_negative_delivery_days_raises(self):
        with self.assertRaises(ValidationError):
            self.env['bs.car.variant'].create({
                'name': 'Pkg', 'model_id': self.model.id, 'estimated_delivery_days': -5,
            })

    def test_offer_inverted_date_range_raises(self):
        with self.assertRaises(ValidationError):
            self.env['bs.car.offer'].create({
                'name': 'Promo', 'date_start': '2026-12-31', 'date_end': '2026-01-01',
            })

    def test_offer_valid_date_range_ok(self):
        offer = self.env['bs.car.offer'].create({
            'name': 'Promo', 'date_start': '2026-01-01', 'date_end': '2026-12-31',
        })
        self.assertTrue(offer)

    # --- Master-data delete guards ------------------------------------------
    def _booking_on(self, **vals):
        return self.env['bs.car.booking'].create({
            'customer_phone': '0812345678',
            'brand_id': self.brand.id,
            'model_id': self.model.id,
            **vals,
        })

    def test_delete_model_used_by_booking_blocked(self):
        self._booking_on()
        with self.assertRaises(ValidationError):
            self.model.unlink()

    def test_delete_brand_with_models_blocked(self):
        # Brand has self.model → must not silently cascade-wipe the catalog.
        with self.assertRaises(ValidationError):
            self.brand.unlink()

    def test_delete_dealer_used_by_booking_blocked(self):
        dealer = self.env['bs.car.dealer'].create({'name': 'D'})
        self._booking_on(dealer_id=dealer.id)
        with self.assertRaises(ValidationError):
            dealer.unlink()

    def test_delete_unused_master_data_allowed(self):
        brand = self.env['bs.car.brand'].create({'name': 'Empty Brand'})
        dealer = self.env['bs.car.dealer'].create({'name': 'Idle Dealer'})
        brand.unlink()
        dealer.unlink()
        self.assertFalse(brand.exists())
        self.assertFalse(dealer.exists())
