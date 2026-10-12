/* =====================================================================
   FINANCIAL REPORT  ·  Frappe page "individual-financial"
   ---------------------------------------------------------------------
   This file only lists the parts of the page. Frappe joins them into one script, in the order below, when the page is
   opened; they share one scope, so a function in one file can be called from another. Read README.md in this folder first.

   WHAT THE USER DOES
     1. Picks Company, Month and Year  ->  matching reports appear as cards
     2. Opens a report                 ->  every section is shown as a ledger table
     3. Clicks the marker on any row   ->  a comment channel opens beside it (x or Esc closes it)
     4. Review chips                   ->  Prepare / Level 1 / Level 2 sign off the whole report
     5. Export button                  ->  the whole report, comments and review in one Excel file

   ONE IDEA TO KEEP IN MIND: a comment belongs to a row by its KEY  "note|sectionType|rowIndex".
   The same key is on the table row (tr.dataset.key) and on the saved comment, so counts, markers and colours
   are always looked up by that key (FR.counts[key], FR.rowRoles[key]).
   ===================================================================== */

/* config.js — Names and limits that can be changed in one place: doctype names, field names, the manager role, polling time, quick notes. */
{% include "financial_report_tool/financial_report_tool/page/individual_financial/js/config.js" %}

/* state.js — FR is the one object that holds everything on screen. rowKey and esc are used everywhere. */
{% include "financial_report_tool/financial_report_tool/page/individual_financial/js/state.js" %}

/* helpers.js — Small pure helpers: names, initials, colours, file sizes and dates in the user's own time zone and date format. */
{% include "financial_report_tool/financial_report_tool/page/individual_financial/js/helpers.js" %}

/* api.js — How the page talks to the server: method paths and the multipart POST used for comments with files and for the Excel export. */
{% include "financial_report_tool/financial_report_tool/page/individual_financial/js/api.js" %}

/* page_load.js — Page start: on_page_load builds the shell and starts init (schema, report list, restore the last session). */
{% include "financial_report_tool/financial_report_tool/page/individual_financial/js/page_load.js" %}

/* report_list.js — Finds the doctype fields, loads every report once, works out each report's real month and year, restores the last session. */
{% include "financial_report_tool/financial_report_tool/page/individual_financial/js/report_list.js" %}

/* filter_bar.js — Company / month / year dropdowns and the report cards under them. */
{% include "financial_report_tool/financial_report_tool/page/individual_financial/js/filter_bar.js" %}

/* shell.js — The empty page skeleton (filters, cards, sheet area, chat drawer) and the icons. Built once, filled later. */
{% include "financial_report_tool/financial_report_tool/page/individual_financial/js/shell.js" %}

/* theme_and_keys.js — Light / dark switch, keyboard shortcuts (Esc, /) and the growing comment box. */
{% include "financial_report_tool/financial_report_tool/page/individual_financial/js/theme_and_keys.js" %}

/* open_report.js — Opening a report: fetch it with its comments, then draw legend, navigator and one card per section. */
{% include "financial_report_tool/financial_report_tool/page/individual_financial/js/open_report.js" %}

/* comments_of.js — The Comments of month switch: which report's chat is on screen, the chat column of that month, counts per row. */
{% include "financial_report_tool/financial_report_tool/page/individual_financial/js/comments_of.js" %}

/* report_review.js — Review chips: Prepare, Level 1 and Level 2 sign off the whole report (the server decides who may press which chip). */
{% include "financial_report_tool/financial_report_tool/page/individual_financial/js/report_review.js" %}

/* period_columns.js — FTM, Previous Month and Previous FTM columns, read from the previous month's own report. */
{% include "financial_report_tool/financial_report_tool/page/individual_financial/js/period_columns.js" %}

/* toolbar.js — Section chips, search, Commented only, expand / collapse all, Export button and the N rows / N commented pill of each section. */
{% include "financial_report_tool/financial_report_tool/page/individual_financial/js/toolbar.js" %}

/* table_decoration.js — Tags the stored HTML tables with classes (group, total, result, note pill...); the CSS does the painting. */
{% include "financial_report_tool/financial_report_tool/page/individual_financial/js/table_decoration.js" %}

/* row_markers.js — The comment marker at the end of every row: its key, its count badge and the row description used by the drawer. */
{% include "financial_report_tool/financial_report_tool/page/individual_financial/js/row_markers.js" %}

/* schedule_jump.js — A statement row with a note number jumps to that note; Back to statement returns to the row. */
{% include "financial_report_tool/financial_report_tool/page/individual_financial/js/schedule_jump.js" %}

/* chat_drawer.js — The chat drawer: open the chat of one row, close it, step to the previous or next commented row. */
{% include "financial_report_tool/financial_report_tool/page/individual_financial/js/chat_drawer.js" %}

/* commented_legend.js — The N rows have comments line: counts, reveal a hidden row, open the next commented row. */
{% include "financial_report_tool/financial_report_tool/page/individual_financial/js/commented_legend.js" %}

/* chat_thread.js — One row's conversation: load it, draw people and messages, live refresh, delete. */
{% include "financial_report_tool/financial_report_tool/page/individual_financial/js/chat_thread.js" %}

/* role_colours.js — Yellow Prepare, green Level 1, red Level 2 on initials chips and on the row markers, bars and pills. */
{% include "financial_report_tool/financial_report_tool/page/individual_financial/js/role_colours.js" %}

/* send_comment.js — Send: saves the text and its files in one request, then updates the thread, marker, pills, legend and cards. */
{% include "financial_report_tool/financial_report_tool/page/individual_financial/js/send_comment.js" %}

/* attachments.js — Files in the chat: choose, drop or paste (up to 5), chips in the composer, links and previews inside a message. */
{% include "financial_report_tool/financial_report_tool/page/individual_financial/js/attachments.js" %}

/* export.js — Export: reads every table from the screen and downloads one Excel file with the comments and review. */
{% include "financial_report_tool/financial_report_tool/page/individual_financial/js/export.js" %}

/* styles.js — Adds the stylesheet once. The rules live in the css folder; every rule is scoped under .fr-root. */
{% include "financial_report_tool/financial_report_tool/page/individual_financial/js/styles.js" %}
