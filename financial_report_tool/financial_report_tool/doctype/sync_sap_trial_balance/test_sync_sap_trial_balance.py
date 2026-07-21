# Copyright (c) 2025, Hybrowlabs Pvt Ltd and Contributors
# See license.txt

from frappe.tests.utils import FrappeTestCase

from financial_report_tool.financial_report_tool.doctype.sync_sap_trial_balance.parent_account_model import (
	CONFIDENCE_THRESHOLD,
	ParentAccountModel,
)
from financial_report_tool.financial_report_tool.doctype.sync_sap_trial_balance.sync_sap_trial_balance import (
	_gl_series_root_type,
)


class _FakePipeline:
	"""Stand-in for the fitted sklearn pipeline: returns fixed class probabilities."""

	def __init__(self, proba):
		self._proba = proba

	def predict_proba(self, _x):
		return [self._proba]


def _model(classes, proba, parent_root_type):
	"""Build a ParentAccountModel wired with a fake pipeline (no training / no DB)."""
	model = ParentAccountModel.__new__(ParentAccountModel)
	model.ok = True
	model.classes_ = classes
	model.pipeline = _FakePipeline(proba)
	model.parent_root_type = parent_root_type
	return model


class TestGLSeriesRootType(FrappeTestCase):
	def test_known_series(self):
		self.assertEqual(_gl_series_root_type("10203040"), "Liability")
		self.assertEqual(_gl_series_root_type("20500000"), "Asset")
		self.assertEqual(_gl_series_root_type("30010001"), "Income")
		self.assertEqual(_gl_series_root_type("40000000"), "Expense")
		self.assertEqual(_gl_series_root_type("50000000"), "Expense")
		self.assertEqual(_gl_series_root_type("70000000"), "Equity")

	def test_leading_zeros_and_whitespace_are_ignored(self):
		# Codes are zero-padded upstream; the series is the first significant digit.
		self.assertEqual(_gl_series_root_type("00030001"), "Income")
		self.assertEqual(_gl_series_root_type("  40100 "), "Expense")

	def test_unknown_or_missing_code_returns_none(self):
		self.assertIsNone(_gl_series_root_type("90000000"))  # series 6/8/9 unmapped
		self.assertIsNone(_gl_series_root_type(""))
		self.assertIsNone(_gl_series_root_type(None))


class TestParentAccountModelRootTypeConstraint(FrappeTestCase):
	def test_prediction_skips_mismatched_root_type(self):
		# Highest-probability class is an Asset group, but the GL is a Liability —
		# the model must fall through to the next matching-root-type class.
		model = _model(
			classes=["Assets - X", "Loans - X"],
			proba=[0.7, 0.3],
			parent_root_type={"Assets - X": "Asset", "Loans - X": "Liability"},
		)
		result = model.predict("10203040", "Bank loan", allowed_root_type="Liability")
		self.assertEqual(result["parent_account"], "Loans - X")
		self.assertAlmostEqual(result["confidence"], 0.3)

	def test_unconstrained_prediction_takes_top_class(self):
		model = _model(
			classes=["Assets - X", "Loans - X"],
			proba=[0.7, 0.3],
			parent_root_type={"Assets - X": "Asset", "Loans - X": "Liability"},
		)
		result = model.predict("10203040", "Bank loan", allowed_root_type=None)
		self.assertEqual(result["parent_account"], "Assets - X")

	def test_unknown_parent_root_type_is_allowed_through(self):
		# A parent whose root type we couldn't determine must not be filtered out.
		model = _model(
			classes=["Mystery - X"],
			proba=[0.9],
			parent_root_type={},
		)
		result = model.predict("10203040", "Something", allowed_root_type="Liability")
		self.assertEqual(result["parent_account"], "Mystery - X")

	def test_all_classes_mismatch_returns_none(self):
		model = _model(
			classes=["Assets - X"],
			proba=[0.9],
			parent_root_type={"Assets - X": "Asset"},
		)
		self.assertIsNone(model.predict("10203040", "Loan", allowed_root_type="Liability"))

	def test_confident_flag_uses_threshold(self):
		model = _model(
			classes=["Loans - X"],
			proba=[CONFIDENCE_THRESHOLD + 0.01],
			parent_root_type={"Loans - X": "Liability"},
		)
		result = model.predict("10203040", "Loan", allowed_root_type="Liability")
		self.assertTrue(result["confident"])
