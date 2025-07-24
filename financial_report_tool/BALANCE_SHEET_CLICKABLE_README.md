# Balance Sheet Clickable Implementation

## Overview

This implementation adds clickable functionality to Balance Sheet account rows in the Financial Report Tool. When a user clicks on an account row in the Balance Sheet, the system will automatically scroll to and highlight the corresponding section in the Financial Report Details.

## Features

1. **Clickable Account Rows**: Each account row in the Balance Sheet is now clickable (if it has a corresponding schedule)
2. **Visual Feedback**: Clickable rows have hover effects and visual indicators
3. **Smooth Scrolling**: Automatic smooth scrolling to the target section
4. **Section Highlighting**: Target sections are highlighted for 3 seconds for visual clarity
5. **Cross-Reference**: Uses the `fr_particular.schedule` field to locate corresponding sections

## Implementation Details

### 1. Data Structure Changes

#### Modified Files:
- `financial_report.py` - Main implementation file

#### Changes Made:

**a) `get_balance_sheet_data()` method:**
- Added schedule field retrieval from FR Particular
- Includes schedule information in the data structure

**b) `render_balance_sheet()` method:**
- Added `data-schedule` attributes to account rows
- Added clickable styling and hover effects
- Only applies to rows that have a schedule value

**c) `get_monthly_balance_sheet_data()` method:**
- Added schedule field retrieval for monthly reports
- Includes schedule information in monthly data structure

**d) `render_monthly_balance_sheet()` method:**
- Added `data-schedule` attributes to monthly account rows
- Added clickable styling and hover effects

### 2. HTML Template Changes

#### Modified Files:
- `fixtures/print_format.json` - Print format template

#### Changes Made:

**a) CSS Additions:**
```css
/* Highlight styling for sections */
.section-highlight {
    background-color: #fff3cd !important;
    border: 2pt solid #ffc107 !important;
    border-radius: 5pt;
    transition: all 0.3s ease;
}

/* Clickable row styling */
.clickable-row {
    cursor: pointer;
    transition: background-color 0.2s ease;
}

.clickable-row:hover {
    background-color: #e9ecef !important;
}
```

**b) JavaScript Functionality:**
```javascript
function handleBalanceSheetRowClick(event) {
    const row = event.target.closest('tr');
    if (!row) return;
    
    const schedule = row.getAttribute('data-schedule');
    if (!schedule) return;
    
    // Remove previous highlights
    document.querySelectorAll('.section-highlight').forEach(el => {
        el.classList.remove('section-highlight');
    });
    
    // Find the target section
    const targetSection = document.querySelector(`[data-section="${schedule}"]`);
    if (targetSection) {
        // Scroll to the section
        targetSection.scrollIntoView({ 
            behavior: 'smooth', 
            block: 'start' 
        });
        
        // Highlight the section
        targetSection.classList.add('section-highlight');
        
        // Remove highlight after 3 seconds
        setTimeout(() => {
            targetSection.classList.remove('section-highlight');
        }, 3000);
    }
}
```

**c) HTML Structure Changes:**
- Added `data-section` attributes to Financial Report sections
- Added JavaScript event listeners for clickable rows

### 3. Data Flow

1. **FR Particular Schedule**: Each FR Particular has a `schedule` field that links to an FR Section
2. **Balance Sheet Data**: The schedule value is retrieved and included in the balance sheet data
3. **HTML Generation**: Account rows get `data-schedule` attributes based on the schedule value
4. **Section Mapping**: Financial Report sections get `data-section` attributes
5. **Click Handling**: JavaScript matches `data-schedule` with `data-section` for navigation

## Usage

### For Users:

1. **Generate a Financial Report** with Balance Sheet sections
2. **View the report** in the browser
3. **Click on any account row** in the Balance Sheet table
4. **Observe** the automatic scrolling and highlighting of the corresponding section

### For Developers:

1. **Ensure FR Particulars** have the `schedule` field populated with valid FR Section names
2. **Verify Financial Report sections** have matching names in the `data-section` attributes
3. **Test the functionality** using the provided test file

## Test File

A test file is provided at:
```
apps/financial_report_tool/financial_report_tool/test_balance_sheet_clickable.html
```

This file demonstrates the complete functionality with sample data and can be opened in any web browser for testing.

## Technical Requirements

- **Frappe Framework**: Compatible with Frappe/ERPNext
- **Modern Browser**: Requires JavaScript support for smooth scrolling
- **Data Integrity**: FR Particular schedule fields must be properly populated

## Configuration

### Required Setup:

1. **FR Particular Configuration**:
   - Ensure each FR Particular that should be clickable has a `schedule` field value
   - The schedule value should correspond to an existing FR Section name

2. **FR Section Names**:
   - Section names in Financial Report Details should match the schedule values
   - Names are case-sensitive and must match exactly

### Optional Customization:

1. **Highlight Duration**: Modify the timeout value (currently 3000ms) in the JavaScript
2. **Highlight Styling**: Customize the `.section-highlight` CSS class
3. **Hover Effects**: Modify the `.clickable-row:hover` CSS class

## Troubleshooting

### Common Issues:

1. **No Click Response**:
   - Check if the FR Particular has a `schedule` value
   - Verify the schedule value matches an FR Section name

2. **No Scrolling**:
   - Ensure JavaScript is enabled in the browser
   - Check browser console for JavaScript errors

3. **No Highlighting**:
   - Verify the target section has the correct `data-section` attribute
   - Check if CSS is properly loaded

### Debug Steps:

1. **Inspect Element**: Check if account rows have `data-schedule` attributes
2. **Console Logs**: Add console.log statements to the JavaScript function
3. **Data Verification**: Confirm FR Particular schedule values are correct

## Future Enhancements

1. **Bidirectional Navigation**: Add ability to click on sections to highlight corresponding balance sheet rows
2. **Search Functionality**: Add search/filter capabilities for large reports
3. **Bookmark Support**: Add URL hash support for direct linking to sections
4. **Mobile Optimization**: Improve touch interactions for mobile devices

## Support

For issues or questions regarding this implementation, please refer to the Frappe/ERPNext documentation or contact the development team. 