"""
Generate high-fidelity synthetic 'OCR needed' files to test the system.
Creates scanned-like images and image-only PDFs featuring:
1. Solid black blocks as Logos (detected by area > 2% and ink density > 0.5).
2. Double-ring circle outlines as Stamps/Seals (detected by aspect ratio 0.6-1.6, area > 0.5%, and circularity > 0.4).
3. Thin, wavy ink lines at the bottom as Signatures (detected by y > 60% height, aspect ratio > 3.0, and ink density < 0.15).

Files are placed directly in 'C:\\Users\\DELL\\Downloads\\DocumentSearch\\test_data' to trigger the OCR worker.
"""

import os
import math
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

# Configurations
OUTPUT_DIR = Path(r"C:\Users\DELL\Downloads\DocumentSearch\test_data")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

PAGE_WIDTH = 800
PAGE_HEIGHT = 1000

print(f"Targeting synthetic OCR file generation in: {OUTPUT_DIR}")

def draw_grid_text(draw, start_x, start_y, lines, spacing=25, font=None, fill="black"):
    """Helper to draw clean multiline document text."""
    current_y = start_y
    for line in lines:
        draw.text((start_x, current_y), line, fill=fill, font=font)
        current_y += spacing
    return current_y

def create_scanned_invoice():
    """Generates a scanned invoice image with a Logo and a Seal."""
    print("Generating: scanned_invoice_with_stamps.png...")
    img = Image.new("RGB", (PAGE_WIDTH, PAGE_HEIGHT), color="white")
    draw = ImageDraw.Draw(img)
    
    # 1. Draw a solid Logo at top-left
    # Size: 150x150, area = 22500 px (2.81% of page, which is > 2%)
    draw.rectangle([50, 50, 200, 200], fill="black")
    # Draw some white patterns inside to make it look realistic
    draw.rectangle([70, 70, 180, 180], fill="white")
    draw.rectangle([90, 90, 160, 160], fill="black")
    # Draw some lines inside
    draw.line([(90, 90), (160, 160)], fill="white", width=4)
    draw.line([(160, 90), (90, 160)], fill="white", width=4)
    
    # 2. Draw standard Invoice Text
    invoice_lines = [
        "INVOICE",
        "GE RENEWABLE ENERGY INDIA PVT LTD",
        "Treasury & Cash Management Division",
        "--------------------------------------------------",
        "Invoice Number:   INV-2026-88094",
        "Invoice Date:     May 28, 2026",
        "Payment Terms:    Net 30 Days",
        "Business Unit:    Treasury",
        "Department:       GECC HQ",
        "--------------------------------------------------",
        "Bill To:",
        "GE Capital International Services",
        "Corporate Financial Services Group",
        "100 Beach Road, Singapore 189702",
        "--------------------------------------------------",
    ]
    draw_grid_text(draw, 240, 50, invoice_lines[:3], spacing=25)
    draw_grid_text(draw, 50, 240, invoice_lines[3:], spacing=20)
    
    # Table headers
    draw.line([(50, 550), (750, 550)], fill="black", width=2)
    draw.text((60, 560), "Line Item / Description", fill="black")
    draw.text((450, 560), "Qty", fill="black")
    draw.text((550, 560), "Unit Price", fill="black")
    draw.text((670, 560), "Amount", fill="black")
    draw.line([(50, 585), (750, 585)], fill="black", width=2)
    
    # Table rows
    table_rows = [
        ("01  Liquidity Management Portal License", "1", "USD 45,000", "USD 45,000"),
        ("02  GE Capital Treasury Consulting Retainer", "12 mos", "USD 12,500", "USD 150,000"),
        ("03  Cross-Border FX Hedging Implementation", "1", "USD 28,400", "USD 28,400"),
    ]
    
    y = 600
    for item, qty, price, amt in table_rows:
        draw.text((60, y), item, fill="black")
        draw.text((450, y), qty, fill="black")
        draw.text((550, y), price, fill="black")
        draw.text((670, y), amt, fill="black")
        y += 30
        
    draw.line([(50, y), (750, y)], fill="black", width=2)
    y += 15
    draw.text((500, y), "Subtotal:        USD 223,400", fill="black")
    y += 25
    draw.text((500, y), "Sales Tax (7%):  USD 15,638", fill="black")
    y += 25
    draw.text((500, y), "Total Due:       USD 239,038", fill="black")
    
    # 3. Draw a Stamp/Seal in middle-right
    # Location: x=580, y=300
    # Size: 110x110, aspect ratio = 1.0 (between 0.6 and 1.6)
    # Area = 12100 px (1.51% of page, which is > 0.5%)
    # Draw double-ring circle with text
    draw.ellipse([580, 300, 690, 410], outline="black", width=6)
    draw.ellipse([600, 320, 670, 390], outline="black", width=2)
    draw.text((615, 345), "GECC", fill="black")
    draw.text((618, 360), "SEAL", fill="black")
    
    # 4. Save file
    file_path = OUTPUT_DIR / "scanned_invoice_with_stamps.png"
    img.save(str(file_path), format="PNG")
    print(f"Created successfully: {file_path}")

def create_scanned_contract():
    """Generates a scanned contract image with text, a Logo, and a Signature."""
    print("Generating: scanned_contract_with_signatures.jpg...")
    img = Image.new("RGB", (PAGE_WIDTH, PAGE_HEIGHT), color="white")
    draw = ImageDraw.Draw(img)
    
    # 1. Draw a Logo at top-left
    # Size: 140x140 at x=50, y=50 (19600 px = 2.45% of page, which is > 2%)
    draw.rectangle([50, 50, 190, 190], fill="black")
    draw.ellipse([70, 70, 170, 170], fill="white")
    draw.ellipse([90, 90, 150, 150], fill="black")
    
    # 2. Write Contract Text
    contract_lines = [
        "MUTUAL NON-DISCLOSURE AGREEMENT",
        "GE CAPITALS CORPORATE ARCHIVE DEPARTMENTS",
        "--------------------------------------------------------------------------------",
        "This Mutual Non-Disclosure Agreement ('Agreement') is entered into as of May 28,",
        "2026 ('Effective Date') between GE Capital International Services ('Americas Division')",
        "and CloudFirst Storage Solutions Ltd. ('Vendor').",
        "",
        "1. Purpose. The parties wish to explore a potential business relationship concerning",
        "cloud-based records management and intelligent document indexing services. In connection",
        "with this exploration, each party may disclose proprietary financial or business secrets.",
        "",
        "2. Confidential Information. 'Confidential Information' means any proprietary or non-public",
        "data disclosed by one party to the other, including business plans, client details,",
        "compliance holds, divestiture deal names, and ISO codes.",
        "",
        "3. Standard of Care. The receiving party agrees to protect the disclosing party's",
        "Confidential Information with the same degree of care it uses for its own confidential",
        "records, but no less than a high standard of care. Information shall only be shared with",
        "authorized contractors under active NDAs.",
        "",
        "4. Term. This Agreement shall remain in effect for a period of five (5) years from the",
        "Effective Date, unless terminated earlier by either party with ninety (90) days written notice.",
        "",
        "IN WITNESS WHEREOF, the parties hereto have executed this Agreement.",
        "--------------------------------------------------------------------------------",
    ]
    draw_grid_text(draw, 220, 50, contract_lines[:2], spacing=25)
    draw_grid_text(draw, 50, 220, contract_lines[2:], spacing=20)
    
    # Signatory labels
    draw.text((80, 750), "Authorized Signature for Client:", fill="black")
    draw.text((80, 880), "Name: Vikram Rao", fill="black")
    draw.text((80, 900), "Title: VP Operations, GECC HQ", fill="black")
    
    # 3. Draw a wavy Signature line
    # Must be at the bottom 40% of the page: y > 600
    # Must have aspect ratio > 3.0
    # Must have ink density < 0.15 inside bounding box
    # Bounding Box: x=100, y=780 to x=400, y=850 (cw=300, ch=70, area = 21,000 px)
    points = []
    for px in range(100, 390, 4):
        # Generate wavy loop using sine/cosine functions
        py = 810 + int(15 * math.sin(px * 0.08) + 8 * math.cos(px * 0.18))
        points.append((px, py))
    draw.line(points, fill="black", width=2)
    
    # Signature baseline
    draw.line([(80, 860), (410, 860)], fill="black", width=1)
    
    # 4. Save file
    file_path = OUTPUT_DIR / "scanned_contract_with_signatures.jpg"
    img.save(str(file_path), format="JPEG", quality=90)
    print(f"Created successfully: {file_path}")

def create_scanned_agreement_pdf():
    """Generates a multipage scanned agreement PDF with a Logo, a Seal, and a Signature."""
    print("Generating: scanned_agreement_multipage.pdf...")
    
    # --- Page 1 ---
    p1 = Image.new("RGB", (PAGE_WIDTH, PAGE_HEIGHT), color="white")
    d1 = ImageDraw.Draw(p1)
    
    # Draw Logo at top-left
    d1.rectangle([50, 50, 190, 190], fill="black")
    d1.rectangle([70, 70, 170, 170], fill="white")
    d1.rectangle([90, 90, 150, 150], fill="black")
    
    p1_lines = [
        "GE CAPITALS OUTSOURCING AGREEMENT",
        "Global Financial Operations Division",
        "--------------------------------------------------------------------------------",
        "AGREEMENT NUMBER:   GE-OUT-2026-0914",
        "EFFECTIVE DATE:     June 1, 2026",
        "CONTRACT VALUE:     USD 1,250,000",
        "BUSINESS UNIT:      GE Capital International",
        "--------------------------------------------------------------------------------",
        "This Outsourcing Services Agreement is made by and between GE Capital International",
        "Services (Americas Division) having its head office at GECC HQ, New York, NY,",
        "and CloudFirst Storage Solutions Ltd. having its office at Bangalore, India.",
        "",
        "WHEREAS, GE Capital desires to outsource certain high-volume document ingestion",
        "and optical character recognition (OCR) auditing services to the Service Provider;",
        "",
        "WHEREAS, the Service Provider represents that it possesses the necessary technical",
        "intelligence, including YOLOv8 object detection engines, Tesseract OCR optimization",
        "pipelines, and high-performance neural template memory servers, to successfully",
        "perform the auditing services outlined in this contract;",
        "",
        "NOW, THEREFORE, the parties agree to the following terms and conditions:",
        "",
        "1. SCOPE OF SERVICES",
        "The Service Provider will scan, process, preprocess, index, and audit up to 1,000,000",
        "legacy transaction records and bank statements. The final audit output must be delivered",
        "in structured multi-sheet Excel spreadsheets complying with standard data formats.",
        "",
        "[CONTINUED ON PAGE 2]",
    ]
    draw_grid_text(d1, 220, 50, p1_lines[:2], spacing=25)
    draw_grid_text(d1, 50, 220, p1_lines[2:], spacing=20)
    
    # Draw Stamp on Page 1 (middle-right)
    # Size: 100x100 at x=600, y=420
    d1.ellipse([600, 420, 700, 520], outline="black", width=5)
    d1.ellipse([615, 435, 685, 505], outline="black", width=2)
    d1.text((630, 460), "GECC", fill="black")
    d1.text((628, 475), "AUDIT", fill="black")
    
    # --- Page 2 ---
    p2 = Image.new("RGB", (PAGE_WIDTH, PAGE_HEIGHT), color="white")
    d2 = ImageDraw.Draw(p2)
    
    p2_lines = [
        "GE CAPITALS OUTSOURCING AGREEMENT",
        "Global Financial Operations Division",
        "--------------------------------------------------------------------------------",
        "2. ACCURACY GATES AND SLA",
        "The Service Provider guarantees an overall OCR extraction accuracy of no less than 95.0%",
        "across all documents. If the accuracy of any page falls below 90.0%, that page will",
        "automatically trigger a 'Visual Audit Review' snippet hold. A designated Contract Auditor",
        "will be assigned to visually inspect and accept/reject the visual anomalies.",
        "",
        "3. TERMINATION FOR CAUSE",
        "Failure to maintain a document ingestion success rate above 98.0% for three (3) consecutive",
        "billing cycles shall constitute a material breach, allowing GE Capital to terminate",
        "the Agreement immediately without penalty.",
        "",
        "IN WITNESS WHEREOF, the parties have executed this Outsourcing Agreement as of the date",
        "first written above.",
        "--------------------------------------------------------------------------------",
    ]
    draw_grid_text(d2, 220, 50, p2_lines[:2], spacing=25)
    draw_grid_text(d2, 50, 220, p2_lines[2:], spacing=20)
    
    # Signatures at bottom of Page 2
    d2.text((80, 720), "For GE Capital International:", fill="black")
    d2.text((80, 850), "Name: Rajesh Kumar", fill="black")
    d2.text((80, 870), "Title: CFO, Americas Division", fill="black")
    
    d2.text((450, 720), "For CloudFirst Solutions:", fill="black")
    d2.text((450, 850), "Name: Ananya Desai", fill="black")
    d2.text((450, 870), "Title: Managing Director", fill="black")
    
    # Cursive signature wavy line on bottom-right signature zone of page 2
    # Bounding Box: x=460, y=750 to x=710, y=820 (cw=250, ch=70, area = 17,500 px)
    points_p2 = []
    for px in range(460, 690, 4):
        py = 780 + int(12 * math.cos(px * 0.07) + 8 * math.sin(px * 0.14))
        points_p2.append((px, py))
    d2.line(points_p2, fill="black", width=2)
    d2.line([(450, 830), (710, 830)], fill="black", width=1)
    
    # Save multi-page PDF
    file_path = OUTPUT_DIR / "scanned_agreement_multipage.pdf"
    p1.save(str(file_path), "PDF", save_all=True, append_images=[p2])
    print(f"Created successfully: {file_path}")

def main():
    create_scanned_invoice()
    create_scanned_contract()
    create_scanned_agreement_pdf()
    print("\nAll synthetic OCR-needed files successfully generated in test_data!")

if __name__ == "__main__":
    main()
