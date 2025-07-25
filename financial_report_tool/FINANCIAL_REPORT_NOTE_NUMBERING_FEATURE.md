# Financial Report Note Numbering Feature

## Overview

This feature automatically assigns note numbers to "Consolidation Note" sections in Financial Reports, starting from 4. The note numbers are automatically updated when rows are added, deleted, or moved up/down. Additionally, these note numbers are mapped to corresponding rows in Balance Sheet and Profit & Loss templates based on the schedule field.

## Features

### 1. **Automatic Note Numbering**
- **Starting Number**: Note numbers begin from 4 for consolidation notes
- **Condition**: Only applies to sections where `section_type = "Consolidation Note"` AND `section` field has a value
- **Auto-update**: Note numbers are automatically recalculated when:
  - Rows are added to the grid
  - Rows are deleted from the grid
  - Rows are moved up or down
  - Section type is changed
  - Section is selected/changed

### 2. **Manual Update Button**
- **Button**: "Update Note Numbers" button available in the form
- **Location**: Appears in the "Generate" button group when document is not submitted
- **Function**: Manually triggers note number recalculation

### 3. **Real-time Updates**
- **Grid Operations**: Note numbers update immediately after grid operations
- **Form Refresh**: Note numbers are updated when the form is refreshed
- **Template Loading**: Note numbers are updated after financial report template is loaded

### 4. **Cross-Template Note Number Mapping**
- **Balance Sheet Integration**: Note numbers from Financial Report are mapped to Balance Sheet rows based on schedule
- **Profit & Loss Integration**: Note numbers from Financial Report are mapped to P&L rows based on schedule
- **Monthly Reports**: Note number mapping works for both regular and monthly reports
- **Automatic Fallback**: If no schedule mapping exists, falls back to template note numbers

## Technical Implementation

### Backend (Python)

#### File: `financial_report.py`

**1. `update_consolidation_note_numbers()` Method**
```python
def update_consolidation_note_numbers(self):
    """Update note numbers for consolidation notes starting from 4"""
    note_counter = 4
    for i in self.financial_report_details:
        if i.section_type == "Consolidation Note" and i.section:
            i.note_no = str(note_counter)
            note_counter += 1
        else:
            i.note_no = ""
```

**2. `before_save()` Method Enhancement**
```python
def before_save(self):
    self.update_consolidation_note_numbers()
    # ... existing code ...
```

**3. `on_update_after_submit()` Method**
```python
def on_update_after_submit(self):
    """Update note numbers when rows are modified after submit"""
    self.update_consolidation_note_numbers()
    self.save()
```

**4. Manual Update Method**
```python
@frappe.whitelist()
def update_note_numbers(self):
    """Update note numbers for consolidation notes"""
    self.update_consolidation_note_numbers()
    self.save()
    frappe.msgprint("Note numbers updated successfully!")
```

**5. Balance Sheet Note Number Mapping**
```python
def get_balance_sheet_data(self, template_name):
    # Get note number mapping from financial report details
    schedule_note_mapping = {}
    for detail in self.financial_report_details:
        if detail.section_type == "Consolidation Note" and detail.section and detail.note_no:
            schedule_note_mapping[detail.section] = detail.note_no

    # For each balance sheet row
    for row in balance_sheet_doc.balance_sheet_template_details:
        # Get the schedule from FR Particular
        fr_particular = frappe.get_doc("FR Particular", row.account)
        schedule = getattr(fr_particular, "schedule", "")
        
        # Use note number from financial report details if available, otherwise use template note
        note_no = None
        if schedule and schedule in schedule_note_mapping:
            note_no = schedule_note_mapping[schedule]
        else:
            note_no = row.note
```

**6. Profit & Loss Note Number Mapping**
```python
def get_profit_and_loss_data(self, template_name):
    # Get note number mapping from financial report details
    schedule_note_mapping = {}
    for detail in self.financial_report_details:
        if detail.section_type == "Consolidation Note" and detail.section and detail.note_no:
            schedule_note_mapping[detail.section] = detail.note_no

    # For each P&L row
    for row in profit_and_loss_doc.profit_and_loss_template_details:
        # Get the schedule from FR Particular
        fr_particular = frappe.get_doc("FR Particular", row.account)
        schedule = getattr(fr_particular, "schedule", "")
        
        # Use note number from financial report details if available, otherwise use template note
        note_no = None
        if schedule and schedule in schedule_note_mapping:
            note_no = schedule_note_mapping[schedule]
        else:
            note_no = row.note
```

### Frontend (JavaScript)

#### File: `financial_report.js`

**1. Grid Function Overrides**
```javascript
// Override grid functions for note number updates
if (frm.grid) {
    const originalAddRow = frm.grid.add_row;
    const originalDeleteRow = frm.grid.delete_row;
    const originalMoveRow = frm.grid.move_row;
    
    frm.grid.add_row = function(...args) {
        const result = originalAddRow.apply(this, args);
        setTimeout(() => updateNoteNumbers(frm), 100);
        return result;
    };
    
    frm.grid.delete_row = function(...args) {
        const result = originalDeleteRow.apply(this, args);
        setTimeout(() => updateNoteNumbers(frm), 100);
        return result;
    };
    
    frm.grid.move_row = function(...args) {
        const result = originalMoveRow.apply(this, args);
        setTimeout(() => updateNoteNumbers(frm), 100);
        return result;
    };
}
```

**2. Note Number Update Function**
```javascript
function updateNoteNumbers(frm) {
    if (!frm.doc.financial_report_details) return;
    
    let noteCounter = 4;
    frm.doc.financial_report_details.forEach((row, index) => {
        if (row.section_type === "Consolidation Note" && row.section) {
            row.note_no = noteCounter.toString();
            noteCounter++;
        } else {
            row.note_no = "";
        }
    });
    
    frm.refresh_field('financial_report_details');
}
```

**3. Event Handlers**
```javascript
// Update note numbers after section type change
section_type(frm, cdt, cdn) {
    // ... existing code ...
    setTimeout(() => updateNoteNumbers(frm), 100);
}

// Update note numbers after section change
section: async function(frm, cdt, cdn) {
    await section(frm, cdt, cdn);
    setTimeout(() => updateNoteNumbers(frm), 100);
}
```

## Usage Instructions

### 1. **Creating a Financial Report**
1. Create a new Financial Report
2. Select a Financial Report Template
3. The system will automatically populate the financial report details
4. Note numbers will be automatically assigned to consolidation notes

### 2. **Adding Consolidation Notes**
1. Add a new row in the Financial Report Details grid
2. Set `Section Type` to "Consolidation Note"
3. Select a `Section` from the dropdown
4. Note number will be automatically assigned (starting from 4)

### 3. **Reordering Notes**
1. Use the move up/down arrows in the grid
2. Note numbers will automatically update to maintain sequential order

### 4. **Manual Update**
1. Click the "Update Note Numbers" button
2. System will recalculate and assign note numbers
3. Success message will be displayed

### 5. **Cross-Template Note Number Mapping**
1. **Automatic Mapping**: When you generate a Financial Report, note numbers are automatically mapped to Balance Sheet and P&L rows
2. **Schedule-Based**: Mapping is based on the `schedule` field in FR Particular records
3. **Fallback**: If no schedule mapping exists, the original template note numbers are used
4. **Consistency**: Same note numbers appear across Financial Report, Balance Sheet, and P&L for related items

## Data Structure

### Financial Report Details Child Table
- **`section_type`**: Type of section (Consolidation Note, Profit & Loss, etc.)
- **`section`**: Link to the specific section (FR Section, etc.)
- **`section_name`**: Name of the section (auto-populated)
- **`note_no`**: Note number (auto-assigned for consolidation notes)

### Note Numbering Logic
```
IF section_type == "Consolidation Note" AND section IS NOT EMPTY:
    note_no = sequential_number_starting_from_4
ELSE:
    note_no = ""
```

### Cross-Template Note Number Mapping Logic
```
FOR each row in Balance Sheet/P&L:
    IF fr_particular.schedule EXISTS AND schedule IN financial_report_details:
        note_no = financial_report_details[schedule].note_no
    ELSE:
        note_no = template_row.note
```

## Configuration

### Starting Note Number
- **Default**: 4
- **Location**: Hardcoded in both Python and JavaScript
- **Modification**: Change the value in both `update_consolidation_note_numbers()` method and `updateNoteNumbers()` function

### Conditions for Note Assignment
- **Section Type**: Must be "Consolidation Note"
- **Section Field**: Must have a value (not empty)
- **Automatic**: No manual configuration required

## Troubleshooting

### Common Issues

**1. Note Numbers Not Updating**
- **Cause**: JavaScript errors or timing issues
- **Solution**: Click "Update Note Numbers" button manually
- **Prevention**: Check browser console for JavaScript errors

**2. Wrong Starting Number**
- **Cause**: Inconsistent values in Python and JavaScript
- **Solution**: Ensure both `update_consolidation_note_numbers()` and `updateNoteNumbers()` use the same starting number

**3. Note Numbers Not Sequential**
- **Cause**: Rows with consolidation notes are not consecutive
- **Solution**: Reorder rows or manually update note numbers

### Debug Information

**Check Note Numbers in Database**
```sql
SELECT section_type, section, note_no 
FROM `tabFinancial Report Details` 
WHERE parent = 'YOUR_FINANCIAL_REPORT_NAME'
ORDER BY idx;
```

**Check JavaScript Console**
- Open browser developer tools
- Look for any JavaScript errors in the console
- Check if `updateNoteNumbers()` function is being called

## Future Enhancements

### Potential Improvements

1. **Configurable Starting Number**
   - Add a field in Financial Report to set starting note number
   - Make it configurable per report

2. **Note Number Format**
   - Support for different formats (4, 4.1, 4a, etc.)
   - Custom formatting options

3. **Bulk Operations**
   - Bulk note number updates
   - Import/export note numbering

4. **Validation**
   - Prevent duplicate note numbers
   - Validate note number ranges

5. **Audit Trail**
   - Track note number changes
   - History of note number modifications

## Testing Scenarios

### Test Cases

1. **Basic Note Numbering**
   - Create Financial Report with consolidation notes
   - Verify note numbers start from 4
   - Verify sequential numbering

2. **Row Operations**
   - Add new consolidation note row
   - Delete existing consolidation note row
   - Move consolidation note rows up/down
   - Verify note numbers update correctly

3. **Mixed Content**
   - Mix consolidation notes with other section types
   - Verify only consolidation notes get note numbers
   - Verify other sections have empty note numbers

4. **Edge Cases**
   - No consolidation notes
   - All consolidation notes
   - Empty section fields
   - Invalid section types

5. **Manual Updates**
   - Use "Update Note Numbers" button
   - Verify success message
   - Verify note numbers are correct

## Support

For issues or questions regarding this feature:
1. Check the troubleshooting section above
2. Review browser console for JavaScript errors
3. Verify database values using SQL queries
4. Contact development team for technical support 