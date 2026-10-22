### Financial Report Tool

This Financial Report Tool.

### Installation

You can install this app using the [bench](https://github.com/frappe/bench) CLI:

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app $URL_OF_THIS_REPO --branch develop
bench install-app financial_report_tool
```

### Consolidated Balance Sheet

The `domestic-financials` page displays Balance Sheet particulars in the order and indentation of the **Summary bs** worksheet of `Consol summary format.xlsx` (rows B3:B58). Its amounts come from saved FR Financial Reports, not from the workbook. Yearly, Monthly, FTM, and All FTM views retain their existing columns; Consolidate sums visible companies and subtracts Elimination and Regrouping.

The mapping uses FR Particular IDs from the configured statutory Balance Sheet template. Available equivalents include share capital, other equity, CWIP, receivables, inventory, cash/bank, current assets and liabilities, and the two distinct provisions lines. Net Working Capital is Total Current Assets minus Total Current Liability. Rows without a verifiable equivalent in the statutory report, including gross block, accumulated depreciation, loan subtypes, inventory subtypes, and long-maturity deposits, display blank rather than an invented amount. Review the ID mapping in `financial_report_tool/financial_report_tool/page/domestic_financials/domestic_financials.py` if the site's FR Particular records differ.

The consolidated page selects only `FR Financial Report` records whose report currency is **INR**, including for companies whose functional currency is foreign. Generate an INR report for such a company and period before expecting its column to appear; a local-currency report is not converted by the page and does not enter the total. Fiscal-year and month choices likewise come from INR reports. Foreign-currency trial-balance detail cannot be treated as INR in P&L breakdowns.


### Jan–Dec subsidiaries and Apr–Mar reporting

Configure `FR SAP Company Mapping.fiscal_cycle` as **Jan-Dec** and select the company's Balance Sheet retained-earnings GL. Create Jan–Dec Fiscal Years and Apr–Mar reporting Fiscal Years with distinct names; ERPNext forbids overlapping Fiscal Years assigned to the same company, so keep the overlapping reporting FY unassigned to that company. Configure previous-FY links for each reporting cycle.

Sync SAP TBs under Jan–Dec Fiscal Years and use **Create TB** for each required snapshot. For an Apr–Mar reporting month, open a created SAP TB and choose **Derive Apr-Mar TB**; select the Apr–Mar FY and reporting month. The derivation requires the source year's March TB and the reporting month's TB, plus December for reporting January–March. Source TBs must be complete signed local-currency snapshots; missing or duplicate snapshots, mismatched currencies, and unbalanced results stop the operation. Re-derive affected reporting months after late SAP postings.

P&L Apr–Dec = current Jan–Dec cumulative minus March; P&L Jan–Mar = prior December minus prior March plus current cumulative. Balance Sheet uses the current calendar-month balance; excluded Jan–Mar profit moves into the configured retained-earnings GL. Reports use the selected Fiscal Year's dates, so create separate `FR Financial Report` records for each cycle and use the Apr–Mar report for consolidation. SAP special periods 13–16 are not fetched by the default sync; include them in an approved year-end source snapshot if required before deriving.

### Contributing

This app uses `pre-commit` for code formatting and linting. Please [install pre-commit](https://pre-commit.com/#installation) and enable it for this repository:

```bash
cd apps/financial_report_tool
pre-commit install
```

Pre-commit is configured to use the following tools for checking and formatting your code:

- ruff
- eslint
- prettier
- pyupgrade

### CI

This app can use GitHub Actions for CI. The following workflows are configured:

- CI: Installs this app and runs unit tests on every push to `develop` branch.
- Linters: Runs [Frappe Semgrep Rules](https://github.com/frappe/semgrep-rules) and [pip-audit](https://pypi.org/project/pip-audit/) on every pull request.


### License

mit
# Financial-Report-Tool
