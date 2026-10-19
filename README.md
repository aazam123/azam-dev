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
