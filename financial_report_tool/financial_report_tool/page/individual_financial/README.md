# Individual Financial page

The page where a finance user picks a company, month and year, opens a **Financial Report**, reads every section as a table,
chats on any row (with files), signs the report off with the review chips, and exports everything to Excel.

## How the files fit together

```
individual_financial/
├── individual_financial.json   Frappe Page record (name, roles)
├── individual_financial.js     ENTRY: only a list of {% include %} lines; Frappe joins them into one script
├── individual_financial.py     Server: export_report (builds the Excel file)
├── js/                         the code, one file per job (all share one scope)
└── css/                        the styles, one file per part of the screen
```

Frappe reads `individual_financial.js`, replaces every `{% include "…" %}` with the file's text, in the order written there, and sends
**one** script to the browser. Nothing else is loaded, so the files can call each other's functions directly.
The order matters only for things that run at once when the script loads (`config`, `state`, then the rest); functions are
declared first and used later, so the order of the other files is free. If you add a file, add its include line to the entry file.

The same trick builds the stylesheet: `js/styles.js` includes the `css/*.css` files inside one template string and adds it to `<head>` once.
That is why the CSS files must not contain a backtick, a `${` or a backslash (write the arrow as `↗`, not `\2197`).

## The JS files (`js/`), in load order

| File | What it does |
|---|---|
| `config.js` | Names and limits to change in one place: doctype names, field names, manager role, polling time, quick notes |
| `state.js` | `FR`, the one object holding everything on screen, plus `rowKey` and `esc` |
| `helpers.js` | Names, initials, colours, file sizes, and dates in the user's own time zone and date format |
| `api.js` | Server method paths and `postForm` (multipart POST, also used for the Excel download) |
| `page_load.js` | `on_page_load`: builds the shell, starts `init` |
| `report_list.js` | Reads the doctype's fields, loads every report once, works out each report's real month and year, restores the last session |
| `filter_bar.js` | Company / month / year dropdowns and the report cards |
| `shell.js` | Icons and the empty page skeleton (filters, cards, sheet area, chat drawer). Built once |
| `theme_and_keys.js` | Light / dark switch, keyboard shortcuts (Esc, `/`), the growing comment box |
| `open_report.js` | `selectReport` → `loadReport` (report + its comments) → `renderReport` |
| `comments_of.js` | The "Comments of" month switch and the chat column of that month |
| `report_review.js` | Review chips: Prepare / Level 1 / Level 2 sign off the whole report |
| `period_columns.js` | FTM, Previous Month and Previous FTM columns, read from the previous month's own report |
| `toolbar.js` | Section chips, search, Commented only, expand all, Export button, the "N commented" pill of each section |
| `table_decoration.js` | Tags the stored HTML tables with classes (group, total, result, note pill); the CSS paints them |
| `row_markers.js` | The comment marker at the end of every row |
| `schedule_jump.js` | A row with a note number jumps to that note; "Back to statement" returns |
| `chat_drawer.js` | Open / close the chat drawer of one row, previous / next commented row |
| `commented_legend.js` | The "N rows have comments" line |
| `chat_thread.js` | One row's conversation: load, draw, live refresh, delete |
| `role_colours.js` | Yellow Prepare, green Level 1, red Level 2 on chips, markers, bars and pills |
| `send_comment.js` | Send: text and files in one request, then update the screen |
| `attachments.js` | Choose / drop / paste files (up to 5), chips in the composer, links and previews in a message |
| `export.js` | Reads every table from the screen and downloads the Excel file |
| `styles.js` | Adds the stylesheet once |

## The CSS files (`css/`), in order

`tokens` (colours, dark theme) · `filter_panel` · `layout` · `report_review` · `legend` · `toolbar` · `notes` · `tables` ·
`margin_marker` · `comment_channel` (drawer, messages, attachments, role colours) · `empty_loading` · `responsive` · `accessibility` · `print`.
Every rule starts with `.fr-root`, so nothing leaks into the rest of Desk. Table cells use `!important` because the stored HTML has inline styles.

## The one idea

A comment belongs to a row by its **key**: `note|sectionType|rowIndex`. The same key is on the table row (`tr.dataset.key`) and on the
saved comment, so counts, markers and colours are always looked up by it (`FR.counts[key]`, `FR.rowRoles[key]`).

## Server side

| What | Where |
|---|---|
| Comments, files, soft delete, role colours | `doctype/financial_report_comments/financial_report_comments.py` — `add_comment`, `get_thread`, `delete_comment`, `get_role_users` |
| Review sign-off (one record per report and role) | `doctype/financial_report_review/` — `get_review_state`, `set_review` |
| Excel export | `page/individual_financial/individual_financial.py` — `export_report` |

Roles: **Comment finance Prepare** (yellow), **Reviewer Level 1** (green), **Reviewer Level 2** (red). Only a **Financial Report Manager** can write.

## Working on it

* Find the file by the job it does (table above), change it, reload the page. In developer mode there is nothing to build.
* Frappe caches a page script in the browser; hard-reload (Ctrl+Shift+R) once after changing a file.
* A new feature gets its own file in `js/` (and `css/`) and one include line in `individual_financial.js`.
* Keep the CSS files free of backticks, `${` and backslashes, or the stylesheet will break silently.
