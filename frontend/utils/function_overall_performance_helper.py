import pandas as pd
# from io import BytesIO
# from openpyxl import Workbook
# from openpyxl.styles import Font, Alignment, Border, Side
from django.http import JsonResponse, HttpResponse

# --- Helper function to generate Overall Summary Table ---
def generate_summary_table(machines, date_range, date_headers, data):
    table_data = {
        'headers': ['Machine'] + [h['full_display'] for h in date_headers] + ['Total'],
        'rows': [],
        'totals_row': ['Total'] + [0.0] * len(date_range) + [0.0]
    }
    # Available time in seconds for a full day
    AVAILABLE_TIME_DAY = 86400   # 24h * 60m * 60s

    for machine in machines:
        row = {'machine': machine, 'cells': [], 'total_npt': 0.0}
        for date_obj in date_range:
            npt_sec = data[machine][date_obj]['total_npt']   # assume now in SECONDS
            percentage = (npt_sec / AVAILABLE_TIME_DAY * 100) if AVAILABLE_TIME_DAY > 0 else 0
            row['cells'].append({
                'npt': npt_sec,
                'display': f"{npt_sec:.0f} ({percentage:.1f}%)"
            })
            row['total_npt'] += npt_sec
        
        total_available = len(date_range) * AVAILABLE_TIME_DAY
        total_percentage = (row['total_npt'] / total_available * 100) if total_available > 0 else 0
        row['total_display'] = f"{row['total_npt']:.0f} ({total_percentage:.1f}%)"
        table_data['rows'].append(row)

        for i, cell in enumerate(row['cells']):
            table_data['totals_row'][i + 1] += cell['npt']

    # Finalize totals row
    total_machines = len(machines) if machines else 1
    for i in range(1, len(table_data['totals_row']) - 1):
        npt_total = table_data['totals_row'][i]
        available = total_machines * AVAILABLE_TIME_DAY
        percentage = (npt_total / available * 100) if available > 0 else 0
        table_data['totals_row'][i] = f"{npt_total:.0f} ({percentage:.1f}%)"
    
    grand_total_npt = sum(r['total_npt'] for r in table_data['rows'])
    grand_total_available = total_machines * len(date_range) * AVAILABLE_TIME_DAY
    grand_total_percentage = (grand_total_npt / grand_total_available * 100) if grand_total_available > 0 else 0
    table_data['totals_row'][-1] = f"{grand_total_npt:.0f} ({grand_total_percentage:.1f}%)"
    
    return table_data


# --- Helper function to generate Shift Table ---
def generate_shift_table(shift, shift_id, machines, date_range, date_headers, data):
    # Available time in seconds for a standard 8-hour shift
    AVAILABLE_TIME_SHIFT = 28800   # 8h * 60m * 60s

    table_data = {
        'shift_name': f"Shift {shift_id.upper()} ({shift.start_time.strftime('%H:%M')} - {shift.end_time.strftime('%H:%M')})",
        'headers': ['Machine'] + [h['full_display'] for h in date_headers] + ['Total'],
        'rows': [],
        'totals_row': ['Total'] + [0.0] * len(date_range) + [0.0]
    }

    for machine in machines:
        row = {'machine': machine, 'cells': [], 'total_npt': 0.0}
        for date_obj in date_range:
            npt_sec = data[machine][date_obj]['shifts'][shift_id]['npt']  # assume in seconds
            percentage = (npt_sec / AVAILABLE_TIME_SHIFT * 100) if AVAILABLE_TIME_SHIFT > 0 else 0
            row['cells'].append({
                'npt': npt_sec,
                'display': f"{npt_sec:.0f} ({percentage:.1f}%)"
            })
            row['total_npt'] += npt_sec
        
        total_available = len(date_range) * AVAILABLE_TIME_SHIFT
        total_percentage = (row['total_npt'] / total_available * 100) if total_available > 0 else 0
        row['total_display'] = f"{row['total_npt']:.0f} ({total_percentage:.1f}%)"
        table_data['rows'].append(row)

        for i, cell in enumerate(row['cells']):
            table_data['totals_row'][i + 1] += cell['npt']

    # Finalize totals row
    total_machines = len(machines) if machines else 1
    for i in range(1, len(table_data['totals_row']) - 1):
        npt_total = table_data['totals_row'][i]
        available = total_machines * AVAILABLE_TIME_SHIFT
        percentage = (npt_total / available * 100) if available > 0 else 0
        table_data['totals_row'][i] = f"{npt_total:.0f} ({percentage:.1f}%)"

    grand_total_npt = sum(r['total_npt'] for r in table_data['rows'])
    grand_total_available = total_machines * len(date_range) * AVAILABLE_TIME_SHIFT
    grand_total_percentage = (grand_total_npt / grand_total_available * 100) if grand_total_available > 0 else 0
    table_data['totals_row'][-1] = f"{grand_total_npt:.0f} ({grand_total_percentage:.1f}%)"

    return table_data


# --- REQUIREMENT 5: Excel Export Function ---
# def export_single_table_to_excel(table_data, sheet_name, date_from, date_to):
#     """
#     Exports a single table to Excel and returns it as an HttpResponse.
#     """
#     output = BytesIO()
#     wb = Workbook()
#     ws = wb.active
#     ws.title = sheet_name
    
#     # Define styles
#     header_font = Font(bold=True, name='Calibri', size=11)
#     center_align = Alignment(horizontal='center', vertical='center')
    
#     # Write headers
#     ws.append(table_data['headers'])
#     for cell in ws[1]:
#         cell.font = header_font
#         cell.alignment = center_align
    
#     # Write data rows
#     for row_data in table_data['rows']:
#         row_list = [row_data['machine']] + [cell['display'] for cell in row_data['cells']] + [row_data['total_display']]
#         ws.append(row_list)
    
#     # Write totals row
#     ws.append(table_data['totals_row'])
#     for cell in ws[ws.max_row]:
#         cell.font = header_font
    
#     # Auto-adjust column widths
#     for column in ws.columns:
#         max_length = 0
#         column_letter = column[0].column_letter
#         for cell in column:
#             try:
#                 if len(str(cell.value)) > max_length:
#                     max_length = len(str(cell.value))
#             except:
#                 pass
#         adjusted_width = min(max_length + 2, 50)
#         ws.column_dimensions[column_letter].width = adjusted_width
    
#     # Save and return
#     wb.save(output)
#     output.seek(0)
    
#     # Generate filename with timestamp
#     timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
#     filename = f"{sheet_name}_{date_from}_to_{date_to}_{timestamp}.xlsx"
    
#     response = HttpResponse(
#         output.getvalue(),
#         content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
#     )
#     response['Content-Disposition'] = f'attachment; filename="{filename}"'
#     return response


# def export_tables_to_excel(table1_data, shift_tables, date_from, date_to):
#     """
#     Your existing function - keep this for full export functionality if needed
#     """
#     output = BytesIO()
#     wb = Workbook()
    
#     # Define some basic styles
#     header_font = Font(bold=True, name='Calibri', size=11)
#     center_align = Alignment(horizontal='center', vertical='center')

#     # --- Sheet 1: Overall NPT Summary ---
#     ws = wb.active
#     ws.title = "Overall NPT Summary"
    
#     # Write headers
#     ws.append(table1_data['headers'])
#     for cell in ws[1]:
#         cell.font = header_font
#         cell.alignment = center_align

#     # Write data rows
#     for row_data in table1_data['rows']:
#         row_list = [row_data['machine']] + [cell['display'] for cell in row_data['cells']] + [row_data['total_display']]
#         ws.append(row_list)
    
#     # Write totals row
#     ws.append(table1_data['totals_row'])
#     for cell in ws[ws.max_row]: # Style the last row
#         cell.font = header_font

#     # --- Subsequent Sheets: Shift-wise Data ---
#     for shift_id, data in shift_tables.items():
#         ws = wb.create_sheet(title=f"Shift {shift_id.upper()}")
        
#         ws.append(data['headers'])
#         for cell in ws[1]:
#             cell.font = header_font
#             cell.alignment = center_align
        
#         for row_data in data['rows']:
#             row_list = [row_data['machine']] + [cell['display'] for cell in row_data['cells']] + [row_data['total_display']]
#             ws.append(row_list)
        
#         ws.append(data['totals_row'])
#         for cell in ws[ws.max_row]:
#             cell.font = header_font

#     # --- Save and Return ---
#     wb.save(output)
#     output.seek(0)
    
#     filename = f"NPT_Summary_{date_from}_to_{date_to}.xlsx"
#     response = HttpResponse(
#         output.getvalue(),
#         content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
#     )
#     response['Content-Disposition'] = f'attachment; filename="{filename}"'
#     return response
