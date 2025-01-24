# -*- coding: utf-8 -*-
import os
import re
import pdfplumber

# Nurodykite savo pagrindinį katalogą, kur yra subkatalogai
import sys
print(f"Current working directory: {os.getcwd()}")
BASE_DIR = os.path.join(os.getcwd(), "testPDFsFolder")
print(f"Looking for PDFs in: {BASE_DIR}")

if not os.path.exists(BASE_DIR):
    print(f"Error: Directory {BASE_DIR} does not exist!")
    sys.exit(1)

# Reguliarioji išraiška tikrinanti failo pavadinimą, pvz. "351708-351708-1.pdf"
pdf_name_pattern = re.compile(r'^\d+-\d+-\d+\.pdf$', re.IGNORECASE)

# Reguliariosios išraiškos šablonai vertėms ištraukti
invoice_pattern = re.compile(r"Invoice\s+(\d+)")  # Pattern for invoice number
bestillingsnr_pattern = re.compile(r"Bestillingsnr\.:\s*(?:ORDER\s+)?([^\n]+)")
leverandor_pattern = re.compile(r"Leverandør:\s*([^\n]+)")

# Šablonai lentelės duomenims
# KID yra pirmame stulpelyje
kid_pattern = re.compile(r"KID:\s*(\d+)")

# Mva. beløp yra stulpelyje (ieškome po "Mva. beløp" žodžių)
mva_belop_pattern = re.compile(r"beløp\s+(\d+[.,]\d+)")

# Total yra paskutiniame stulpelyje (po "NOK" arba tiesiog "Total")
total_pattern = re.compile(r"(?:NOK|Valuta)\s+Total\s*\n*(\d+[.,]\d+)")

# Papildomi šablonai
alt_kid_pattern = re.compile(r"KID\s+(\d+)")
alt_mva_pattern = re.compile(r"Mva\.\s*beløp\s+(\d+[.,]\d+)")
alt_total_pattern = re.compile(r"Total\s*\n*(\d+[.,]\d+)")

# Funkcija lentelės eilutės analizei
def parse_table_row(text, row_pattern):
    match = row_pattern.search(text)
    if match:
        return match.group(1)
    return None

# Funkcija eilutės išvalymui nuo nereikalingų simbolių
def clean_text(text):
    if text:
        # Pašaliname visus nereikalingus tarpus
        text = ' '.join(text.split())
        return text.strip()
    return None

# Funkcija skaičių formatavimui
def format_number(value):
    if value:
        # Pašaliname tarpus
        value = value.replace(" ", "")
        # Pakeičiame kablelius į taškus
        value = value.replace(",", ".")
        return value
    return None

# Debug print to see what files we're finding
print("Starting PDF processing...")

for root, dirs, files in os.walk(BASE_DIR):
    print(f"\nScanning directory: {root}")
    print(f"Found files: {files}")
    
    for filename in files:
        # Tikrinam, ar failo pavadinimas atitinka "xxxxx-xxxxx-x.pdf" formatą
        print(f"Checking file: {filename}")
        if pdf_name_pattern.match(filename):
            print(f"Found matching PDF: {filename}")
            pdf_path = os.path.join(root, filename)
            
            try:
                with pdfplumber.open(pdf_path) as pdf:
                    # Extract text only from the first page
                    full_text = pdf.pages[0].extract_text() or ""
                    
                    print(f"\nExtracted text from {filename}:")
                    print("=" * 50)
                    print(full_text)
                    print("=" * 50)
                    
                    # Ištraukiame visas reikšmes, bandant alternatyvius šablonus jei reikia
                    bestillingsnr_match = bestillingsnr_pattern.search(full_text)
                    if not bestillingsnr_match:
                        bestillingsnr_match = alt_bestillingsnr_pattern.search(full_text)
                    
                    leverandor_match = leverandor_pattern.search(full_text)
                    
                    kid_match = kid_pattern.search(full_text)
                    if not kid_match:
                        kid_match = alt_kid_pattern.search(full_text)
                    
                    mva_belop_match = mva_belop_pattern.search(full_text)
                    if not mva_belop_match:
                        mva_belop_match = alt_mva_pattern.search(full_text)
                    
                    total_match = total_pattern.search(full_text)
                    
                    print("\nMatches found:")
                    print(f"Bestillingsnr match: {bestillingsnr_match.group(1) if bestillingsnr_match else 'Not found'}")
                    print(f"Leverandor match: {leverandor_match.group(1) if leverandor_match else 'Not found'}")
                    print(f"KID match: {kid_match.group(1) if kid_match else 'Not found'}")
                    print(f"Mva belop match: {mva_belop_match.group(1) if mva_belop_match else 'Not found'}")
                    print(f"Total match: {total_match.group(1) if total_match else 'Not found'}")
                    
                    # Extract invoice number
                    invoice_match = invoice_pattern.search(full_text)
                    print(f"Invoice match: {invoice_match.group(1) if invoice_match else 'Not found'}")
                    
                    # Išgauname ir formatuojame reikšmes
                    invoice = clean_text(invoice_match.group(1)) if invoice_match else None
                    bestillingsnr = clean_text(bestillingsnr_match.group(1)) if bestillingsnr_match else None
                    leverandor = clean_text(leverandor_match.group(1)) if leverandor_match else None
                    kid = kid_match.group(1).strip() if kid_match else None
                    
                    # Ieškome reikšmių lentelėje
                    # Pirma ieškome eilutės su antraštėmis
                    header_pattern = re.compile(r"KID:\s*Mva\.\s*Mva\.Gr\.lag\s*Mva\.\s*beløp\s*Valuta\s*Total\s*\n")
                    header_match = header_pattern.search(full_text)
                    
                    print("\nTable pattern search results:")
                    if header_match:
                        print("Found table header!")
                        # Ieškome reikšmių eilutės po antraštėmis
                        values_start = header_match.end()
                        values_line = full_text[values_start:values_start+100].split('\n')[0]
                        print(f"Values line: {values_line}")
                        
                        # Išskaidome reikšmių eilutę
                        values = values_line.strip().split()
                        if len(values) >= 6:
                            kid = values[0]
                            mva_grlag = format_number(values[2])  # Third element is Mva.Gr.lag
                            mva_belop = format_number(values[3])  # Fourth element is Mva. beløp
                            total = format_number(values[5])      # Sixth element is Total
                            print(f"Extracted - KID: {kid}, Mva.Gr.lag: {mva_grlag}, Mva. beløp: {mva_belop}, Total: {total}")
                    else:
                        print("No table match found, trying individual patterns...")
                        
                        # Bandome rasti Mva. beløp
                        mva_belop = None
                        if mva_belop_match:
                            print(f"Found Mva. beløp with primary pattern: {mva_belop_match.group(1)}")
                            mva_belop = format_number(mva_belop_match.group(1))
                        elif alt_mva_pattern.search(full_text):
                            alt_match = alt_mva_pattern.search(full_text)
                            print(f"Found Mva. beløp with alternative pattern: {alt_match.group(1)}")
                            mva_belop = format_number(alt_match.group(1))
                        else:
                            print("No Mva. beløp match found")
                        
                        # Initialize mva_grlag
                        mva_grlag = None
                        
                        # Bandome rasti Total
                        total = None
                        if total_match:
                            print(f"Found Total with primary pattern: {total_match.group(1)}")
                            total = format_number(total_match.group(1))
                        elif alt_total_pattern.search(full_text):
                            alt_match = alt_total_pattern.search(full_text)
                            print(f"Found Total with alternative pattern: {alt_match.group(1)}")
                            total = format_number(alt_match.group(1))
                        else:
                            print("No Total match found")
                    
                    # Spausdiname rezultatą
                    if all([invoice, bestillingsnr, leverandor, kid, mva_belop, mva_grlag, total]):
                        print(f"\nFailas: {filename}")
                        print(f"Katalogas: {root}")
                        print(f"Fakturanr.: {invoice}")
                        print(f"Leverandør: {leverandor}")
                        print(f"Bestillingsnr.: {bestillingsnr}")
                        print(f"KID: {kid}")
                        print(f"Mva.Gr.lag: {mva_grlag}")
                        print(f"Mva. beløp: {mva_belop}")
                        print(f"Total: {total}")
                        print("-" * 50)
                    else:
                        print(f"({root}) Nepavyko rasti visų reikiamų duomenų faile: {filename}")
            
            except Exception as e:
                print(f"Klaida apdorojant failą {pdf_path}: {e}")
