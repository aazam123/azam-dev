import frappe

@frappe.whitelist()
def get_entries(fiscal_year, month, company):

    return frappe.get_all(
        "FR Console Trial Balance",
        filters={
            "fiscal_year": fiscal_year,
            "month": month,
            "company": company
        },
        fields=[
            "name",
            "gl_account",
            "currency",
            "amount",
            "exchange_rate",
            "amount_inr",
            "report_type"
        ],
        limit_page_length=1000
    )


@frappe.whitelist()
def update_entries(fiscal_year, month, company, update_closing, update_average, updated_rows=None):

    update_closing = int(update_closing)
    update_average = int(update_average)

    updated_rows = frappe.parse_json(updated_rows) if updated_rows else []

    # ❗ Validation
    if not update_closing and not update_average and not updated_rows:
        frappe.throw("Please select at least one option")

    # 🔹 Step 1: Update report_type & track changed rows
    changed_names = set()

    for row in updated_rows:
        frappe.db.set_value(
            "FR Console Trial Balance",
            row["name"],
            "report_type",
            row["report_type"]
        )
        changed_names.add(row["name"])

    # 🔹 Step 2: Fetch all entries
    entries = frappe.get_all(
        "FR Console Trial Balance",
        filters={
            "fiscal_year": fiscal_year,
            "month": month,
            "company": company
        },
        fields=["name", "amount", "currency", "report_type"]
    )

    # 🔹 Step 3: Apply exchange logic
    for row in entries:

        exchange_rate = None

        # ✅ CASE 1: Report type changed → ALWAYS recalculate
        if row.name in changed_names:

            if row.report_type == "Profit and Loss":
                exchange_rate = get_closing_rate(row.currency, month, fiscal_year)

            elif row.report_type == "Balance Sheet":
                exchange_rate = get_average_rate(row.currency, month, fiscal_year)

        # ✅ CASE 2: Bulk update via checkbox
        else:
            if update_closing and row.report_type == "Profit and Loss":
                exchange_rate = get_closing_rate(row.currency, month, fiscal_year)

            elif update_average and row.report_type == "Balance Sheet":
                exchange_rate = get_average_rate(row.currency, month, fiscal_year)

        # 🔹 Apply update
        if exchange_rate is not None:
            amount_inr = (row.amount or 0) * exchange_rate

            frappe.db.set_value(
                "FR Console Trial Balance",
                row.name,
                {
                    "exchange_rate": exchange_rate,
                    "amount_inr": amount_inr
                }
            )

    frappe.db.commit()

    return "Success"

def get_closing_rate(currency, month, fiscal_year):

    if currency == "INR":
        return 1

    return frappe.db.get_value(
        "FR Foreign Exchange Rate",
        {
            "from_currency": currency,
            "to_currency": "INR",
            "month": month,
            "fiscal_year": fiscal_year
        },
        "closing_rate"
    ) or 1


def get_average_rate(currency, month, fiscal_year):

    if currency == "INR":
        return 1

    return frappe.db.get_value(
        "FR Foreign Exchange Rate",
        {
            "from_currency": currency,
            "to_currency": "INR",
            "month": month,
            "fiscal_year": fiscal_year
        },
        "average_rate"
    ) or 1