# -*- coding: utf-8 -*-
import os
import re
import pdfplumber
import pandas as pd
from datetime import datetime
import sys

def get_base_dir():
    if len(sys.argv) > 1:
        base_dir = sys.argv[1]
        if not os.path.exists(base_dir):
            print(f"Error: Directory {base_dir} does not exist!")
            sys.exit(1)
        return base_dir
    else:
        print("Error: Please provide a directory path as argument")
        print("Usage: python pdf_reader.py <directory_path>")
        sys.exit(1)

# Get the base directory from command line argument
print(f"Current working directory: {os.getcwd()}")
BASE_DIR = get_base_dir()
print(f"Looking for PDFs in: {BASE_DIR}")

# Regular expressions for file name and data extraction
pdf_name_pattern = re.compile(r'^\d+-\d+-\d+\.pdf$', re.IGNORECASE)
invoice_pattern = re.compile(r"Invoice\s+(\d+)")
bestillingsnr_pattern = re.compile(r"Bestillingsnr\.:\s*([^\n]+)")
leverandor_pattern = re.compile(r"Leverandør:\s*([^\n]+)")
kid_pattern = re.compile(r"KID:\s*(\d+)")
mva_belop_pattern = re.compile(r"beløp\s+(\d+[.,]\d+)")
total_pattern = re.compile(r"(?:NOK|Valuta)\s+Total\s*\n*(\d+[.,]\d+)")
alt_kid_pattern = re.compile(r"KID\s+(\d+)")
alt_mva_pattern = re.compile(r"Mva\.\s*beløp\s+(\d+[.,]\d+)")
alt_total_pattern = re.compile(r"Total\s*\n*(\d+[.,]\d+)")

def clean_text(text):
    if text:
        text = ' '.join(text.split())
        text = re.sub(r'(?i)order\b', 'Order', text)
        return text.strip()
    return None

def clean_vendor_name(text):
    if text:
        # Take only the part before the dash and strip whitespace
        return text.split('-')[0].strip()
    return None

def format_number(value):
    if value:
        value = value.replace(" ", "")
        value = value.replace(",", ".")
        return value
    return None

# Initialize list to store all extracted data
extracted_data = []

print("Starting PDF processing...")

for root, dirs, files in os.walk(BASE_DIR):
    print(f"\nScanning directory: {root}")
    print(f"Found files: {files}")
    
    for filename in files:
        print(f"Checking file: {filename}")
        if pdf_name_pattern.match(filename):
            print(f"Found matching PDF: {filename}")
            pdf_path = os.path.join(root, filename)
            
            try:
                with pdfplumber.open(pdf_path) as pdf:
                    full_text = pdf.pages[0].extract_text() or ""
                    
                    # Extract all values using patterns
                    bestillingsnr_match = bestillingsnr_pattern.search(full_text)
                    leverandor_match = leverandor_pattern.search(full_text)
                    kid_match = kid_pattern.search(full_text) or alt_kid_pattern.search(full_text)
                    mva_belop_match = mva_belop_pattern.search(full_text) or alt_mva_pattern.search(full_text)
                    total_match = total_pattern.search(full_text) or alt_total_pattern.search(full_text)
                    invoice_match = invoice_pattern.search(full_text)
                    
                    # Initialize data dictionary
                    row_data = {
                        "Mva.Gr.lag": None,
                        "Mva. beløp:": None,
                        "Total": None,
                        "Bestillingsnr.": None,
                        "Fakturanr.": None,
                        "Leverandør:": None,
                        "KID": None
                    }
                    
                    # Extract table values
                    header_pattern = re.compile(r"KID:\s*Mva\.\s*Mva\.Gr\.lag\s*Mva\.\s*beløp\s*Valuta\s*Total\s*\n")
                    header_match = header_pattern.search(full_text)
                    
                    if header_match:
                        values_start = header_match.end()
                        values_line = full_text[values_start:values_start+100].split('\n')[0]
                        values = values_line.strip().split()
                        
                        if len(values) >= 6:
                            row_data.update({
                                "KID": values[0],
                                "Mva.Gr.lag": format_number(values[2]),
                                "Mva. beløp:": format_number(values[3]),
                                "Total": format_number(values[5])
                            })
                    
                    # Update remaining values
                    if not row_data["Mva. beløp:"] and mva_belop_match:
                        row_data["Mva. beløp:"] = format_number(mva_belop_match.group(1))
                    
                    if not row_data["Total"] and total_match:
                        row_data["Total"] = format_number(total_match.group(1))
                    
                    if not row_data["KID"] and kid_match:
                        row_data["KID"] = kid_match.group(1).strip()
                    
                    row_data.update({
                        "Bestillingsnr.": clean_text(bestillingsnr_match.group(1)) if bestillingsnr_match else None,
                        "Fakturanr.": clean_text(invoice_match.group(1)) if invoice_match else None,
                        "Leverandør:": clean_vendor_name(leverandor_match.group(1)) if leverandor_match else None
                    })
                    
                    # Add to extracted data if all required fields are present
                    if any(row_data.values()):
                        extracted_data.append(row_data)
                        print(f"\nFile: {filename}")
                        for key, value in row_data.items():
                            print(f"{key}: {value}")
                        print("-" * 50)
                    else:
                        print(f"({root}) Could not find all required data in file: {filename}")
            
            except Exception as e:
                print(f"Error processing file {pdf_path}: {e}")

# Create CSV file with current date and add calculations
if extracted_data:
    current_date = datetime.now().strftime("%Y-%m-%d")
    csv_filename = f"faktura data extraction {current_date}.csv"
    
    # Convert to DataFrame
    df = pd.DataFrame(extracted_data)
    
    # Convert numeric columns to float and ensure KID is string
    df['Mva.Gr.lag'] = pd.to_numeric(df['Mva.Gr.lag'], errors='coerce')
    df['Mva. beløp:'] = pd.to_numeric(df['Mva. beløp:'], errors='coerce')
    df['Total'] = pd.to_numeric(df['Total'], errors='coerce')
    df['KID'] = df['KID'].astype(str)
    
    # Calculate totals by vendor with rounding
    totals_by_vendor = df.groupby('Leverandør:').agg({
        'Mva.Gr.lag': lambda x: round(x.sum(), 2),
        'Mva. beløp:': lambda x: round(x.sum(), 2),
        'Total': lambda x: round(x.sum(), 2)
    }).reset_index()
    
    # Create empty rows and headers for the summary section
    empty_rows = pd.DataFrame([{col: '' for col in df.columns}] * 2)
    header_row = pd.DataFrame([{
        'Leverandør:': 'TOTALS BY VENDOR:',
        'Mva.Gr.lag': '',
        'Mva. beløp:': '',
        'Total': ''
    }])
    
    # Create vendor totals rows
    vendor_totals = pd.DataFrame([{
        'Mva.Gr.lag': row['Mva.Gr.lag'],
        'Mva. beløp:': row['Mva. beløp:'],
        'Total': row['Total'],
        'Leverandør:': row['Leverandør:']
    } for _, row in totals_by_vendor.iterrows()])
    
    # Create grand totals row with rounding
    grand_total_row = pd.DataFrame([{
        'Mva.Gr.lag': round(df['Mva.Gr.lag'].sum(), 2),
        'Mva. beløp:': round(df['Mva. beløp:'].sum(), 2),
        'Total': round(df['Total'].sum(), 2),
        'Leverandør:': 'GRAND TOTAL'
    }])
    
    # Combine all parts
    final_df = pd.concat([
        df,  # Original data
        empty_rows,  # Separation
        header_row,  # "TOTALS BY VENDOR:" header
        vendor_totals,  # Vendor totals
        pd.DataFrame([{col: '' for col in df.columns}]),  # Empty row before grand total
        grand_total_row  # Grand total row
    ], ignore_index=True)
    
    # Save to CSV
    final_df.to_csv(csv_filename, index=False, encoding='utf-8', float_format='%.2f')
    
    # Print the totals
    print("\nTotals by vendor:")
    for _, row in totals_by_vendor.iterrows():
        print(f"\n{row['Leverandør:']}:")
        print(f"Mva.Gr.lag total: {row['Mva.Gr.lag']:,.2f}")
        print(f"Mva. beløp total: {row['Mva. beløp:']:,.2f}")
        print(f"Total: {row['Total']:,.2f}")
    
    print("\nGRAND TOTALS:")
    print(f"Mva.Gr.lag: {df['Mva.Gr.lag'].sum():,.2f}")
    print(f"Mva. beløp: {df['Mva. beløp:'].sum():,.2f}")
    print(f"Total: {df['Total'].sum():,.2f}")
    
    print(f"\nData has been saved to: {csv_filename}")
else:
    print("\nNo data was extracted from the PDFs")
