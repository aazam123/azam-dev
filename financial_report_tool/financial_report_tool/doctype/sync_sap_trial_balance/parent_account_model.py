# Copyright (c) 2026, Hybrowlabs Pvt Ltd
# For license information, please see license.txt

"""Local ML classifier that suggests a Parent Account for an unmapped GL.

The model learns purely from the company's existing Chart of Accounts — each
posting (non-group) Account is a training example whose *label* is its
``parent_account`` and whose *features* are its account number (expanded into
hierarchical prefix tokens, since SAP codes are hierarchical) plus its name.

It is trained on the fly per company/load — a few thousand accounts train in
well under a second — so there is no model file to persist or version. When the
top prediction's confidence is below :data:`CONFIDENCE_THRESHOLD`, the caller
treats it as "no existing group fits" and proposes creating a new parent.

scikit-learn is an optional dependency: :func:`sklearn_available` lets callers
fall back to the heuristic suggester when it isn't installed.
"""

import frappe

# Minimum probability for the top predicted parent to be offered as a confident
# match. Below this the caller proposes a new parent instead.
CONFIDENCE_THRESHOLD = 0.35

# Below these, a per-company model can't learn anything useful.
MIN_SAMPLES = 10
MIN_CLASSES = 2

# Cap each vectorizer's vocabulary so training stays fast and bounded on large
# charts of accounts (the biggest companies have a few thousand accounts).
WORD_MAX_FEATURES = 10000
CHAR_MAX_FEATURES = 8000


def sklearn_available():
	try:
		import sklearn  # noqa: F401

		return True
	except Exception:
		return False


def account_text(account_number, account_name):
	"""Feature string for one account: code + hierarchical prefixes + name.

	The prefix tokens (``p3 p31 p314 …``) let the classifier key off shared code
	ranges the way the prefix heuristic does, while the name tokens capture
	semantics for description-only rows.
	"""
	code = (str(account_number) if account_number is not None else "").strip().lstrip("0")
	prefixes = " ".join(f"p{code[:i]}" for i in range(1, len(code) + 1)) if code else ""
	return f"{code} {prefixes} {(account_name or '').lower()}".strip()


class ParentAccountModel:
	"""Per-company parent-account classifier. Check :attr:`ok` before predicting."""

	def __init__(self, company):
		self.company = company
		self.ok = False
		self._fit()

	def _fit(self):
		rows = frappe.get_all(
			"Account",
			filters={"company": self.company, "is_group": 0},
			fields=["account_number", "account_name", "parent_account"],
		)
		samples = [r for r in rows if r.parent_account]
		if len(samples) < MIN_SAMPLES or len({r.parent_account for r in samples}) < MIN_CLASSES:
			return

		try:
			from sklearn.feature_extraction.text import TfidfVectorizer
			from sklearn.linear_model import SGDClassifier
			from sklearn.pipeline import FeatureUnion, Pipeline

			x = [account_text(r.account_number, r.account_name) for r in samples]
			y = [r.parent_account for r in samples]

			# Word features (code prefixes + name unigrams/bigrams) capture the
			# account hierarchy and terminology; char n-grams add robustness to
			# spelling/spacing variants ("Gratuity" vs "Gratuty", "FDOD" vs "FD OD").
			features = FeatureUnion([
				("word", TfidfVectorizer(
					token_pattern=r"[A-Za-z0-9]+", ngram_range=(1, 2),
					sublinear_tf=True, max_features=WORD_MAX_FEATURES,
				)),
				("char", TfidfVectorizer(
					analyzer="char_wb", ngram_range=(3, 4),
					sublinear_tf=True, max_features=CHAR_MAX_FEATURES,
				)),
			])
			# SGD (log-loss) is ~10x faster to train than lbfgs LogisticRegression
			# at the same accuracy, and keeps predict_proba for confidence scoring —
			# important since the model is trained on the fly on every load.
			clf = SGDClassifier(
				loss="log_loss", alpha=1e-5, max_iter=30,
				class_weight="balanced", random_state=0,
			)
			self.pipeline = Pipeline([("features", features), ("clf", clf)])
			self.pipeline.fit(x, y)
			self.classes_ = clf.classes_
			self.ok = True
		except Exception:
			# Any training failure degrades gracefully to the caller's heuristic.
			frappe.log_error(title=f"ParentAccountModel training failed — {self.company}")
			self.ok = False

	def predict(self, gl_code, gl_description):
		"""Return ``{parent_account, confidence (0-1), confident}`` or ``None``."""
		if not self.ok:
			return None

		proba = self.pipeline.predict_proba([account_text(gl_code, gl_description)])[0]
		idx = max(range(len(proba)), key=lambda i: proba[i])
		confidence = float(proba[idx])
		return {
			"parent_account": str(self.classes_[idx]),
			"confidence": confidence,
			"confident": confidence >= CONFIDENCE_THRESHOLD,
		}
