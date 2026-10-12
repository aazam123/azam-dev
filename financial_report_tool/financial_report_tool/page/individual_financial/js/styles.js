/* =====================================================================
   styles.js
   Adds the stylesheet to the page once. The rules are in the css folder, one file per part of the screen, in this order:
   tokens.css, filter_panel.css, layout.css, report_review.css, legend.css, toolbar.css, notes.css, tables.css, margin_marker.css, comment_channel.css, empty_loading.css, responsive.css, accessibility.css, print.css
   Every rule is scoped under .fr-root, and no external file is loaded, so the page can never trigger a 404 for a stylesheet.
   ===================================================================== */

// Adds the page stylesheet to <head> once (a second visit to the page finds it and does nothing).
function injectStyles() {
    if (document.getElementById('fr-styles')) return;

    const style = document.createElement('style');
    style.id = 'fr-styles';
    style.textContent = `
{% include "financial_report_tool/financial_report_tool/page/individual_financial/css/tokens.css" %}
{% include "financial_report_tool/financial_report_tool/page/individual_financial/css/filter_panel.css" %}
{% include "financial_report_tool/financial_report_tool/page/individual_financial/css/layout.css" %}
{% include "financial_report_tool/financial_report_tool/page/individual_financial/css/report_review.css" %}
{% include "financial_report_tool/financial_report_tool/page/individual_financial/css/legend.css" %}
{% include "financial_report_tool/financial_report_tool/page/individual_financial/css/toolbar.css" %}
{% include "financial_report_tool/financial_report_tool/page/individual_financial/css/notes.css" %}
{% include "financial_report_tool/financial_report_tool/page/individual_financial/css/tables.css" %}
{% include "financial_report_tool/financial_report_tool/page/individual_financial/css/margin_marker.css" %}
{% include "financial_report_tool/financial_report_tool/page/individual_financial/css/comment_channel.css" %}
{% include "financial_report_tool/financial_report_tool/page/individual_financial/css/empty_loading.css" %}
{% include "financial_report_tool/financial_report_tool/page/individual_financial/css/responsive.css" %}
{% include "financial_report_tool/financial_report_tool/page/individual_financial/css/accessibility.css" %}
{% include "financial_report_tool/financial_report_tool/page/individual_financial/css/print.css" %}
    `;
    document.head.appendChild(style);
}
