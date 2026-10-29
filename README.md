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

Configure `FR SAP Company Mapping.fiscal_cycle` as **Jan-Dec** and select the company's Balance Sheet retained-earnings GL. No Jan–Dec Fiscal Year is created or needed: use the existing Apr–Mar Fiscal Years, and configure previous-FY links for each of them as usual.

Create one `FR Sync SAP Trial Balance` per snapshot using the Apr–Mar Fiscal Year that contains the month, then **Sync SAP Data** and **Accept** it with **Create TB**. For a Jan-Dec company the sync requests calendar periods `01` through the month's calendar number for the calendar year the month falls in (for example September 2026 under FY 2026-2027 is year 2026, periods 01–09). **Create TB** only marks that snapshot accepted; it writes no `FR Trial Balance Entry` rows, because the data is cumulative from 1 January. Then open an accepted SAP TB and choose **Derive Apr-Mar TB**, selecting the Apr–Mar FY and reporting month. The derivation reads the accepted syncs (matched by company, calendar year and month): the source year's March, the reporting month, and also December for reporting January–March. Source TBs must be complete signed local-currency snapshots; missing or duplicate snapshots, unmapped accounts, mismatched currencies, and unbalanced results stop the operation. Derive refuses to overwrite a non-derived TB for the same month. Re-derive affected reporting months after late SAP postings.

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
