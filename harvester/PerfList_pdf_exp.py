# harvester/PerfList_pdf_exp.py
# =============================================================================
# --- ABSCHNITT 1: IMPORTE UND SETUP ---
# =============================================================================
import os
import re
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm

# --- FESTE LAYOUT-WERTE ---
CELL_PADDING = 1.05

# =============================================================================
# --- ABSCHNITT 2: HILFSFUNKTIONEN (FOOTER & METADATEN) ---
# =============================================================================
def draw_footer(canvas, doc, footer_text):
    """Zeichnet die Fußzeile fix an den unteren Rand jeder Seite."""
    canvas.saveState()
    canvas.setFont('Helvetica', 8)
    canvas.setFillColor(colors.grey)
    # Links: Footer Text aus der GUI
    canvas.drawString(15*mm, 10*mm, footer_text)
    # Rechts: Aktuelles Datum
    now = datetime.now().strftime("%d.%m.%Y")
    canvas.drawRightString(282*mm, 10*mm, f"Date: {now}")
    canvas.restoreState()

# =============================================================================
# --- ABSCHNITT 3: HAUPTFUNKTION ZUR PDF-GENERIERUNG ---
# =============================================================================
def generate_pdf(perf_path, pdf_filepath, footer_text):
    """Wird von der Main.py aufgerufen und erstellt das PDF."""
    if not os.path.exists(perf_path):
        return False, f"Pfad '{perf_path}' not found."

    # Dokumenten-Setup mit Metadaten (Titel: DreamDexed Performanceliste)
    doc = SimpleDocTemplate(pdf_filepath, 
                            pagesize=landscape(A4), 
                            topMargin=10*mm, 
                            bottomMargin=18*mm, 
                            leftMargin=10*mm, 
                            rightMargin=10*mm,
                            title="DreamDexed Performanceliste") # PDF-Titel gesetzt
    
    elements = []
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('BankTitle', fontSize=16, fontName='Helvetica-Bold', spaceAfter=8)

    # Banken sammeln und sortieren
    banks = sorted([d for d in os.listdir(perf_path) if os.path.isdir(os.path.join(perf_path, d))])

    if not banks:
        return False, "No subfolders found in performance directory."

    # =============================================================================
    # --- ABSCHNITT 4: SCHLEIFE ÜBER ALLE BANKEN ---
    # =============================================================================
    for index, bank_name in enumerate(banks):
        bank_dir = os.path.join(perf_path, bank_name)

        # ---- NEU: Dateigrößen prüfen und Typ bestimmen ----
        has_effects = False
        slots = [""] * 128

        for file in os.listdir(bank_dir):
            if file.lower().endswith(".ini"):
                filepath = os.path.join(bank_dir, file)
                # Größe in Bytes (9 kB = 9216 Bytes)
                try:
                    size = os.path.getsize(filepath)
                    if size >= 9216:
                        has_effects = True
                except Exception:
                    pass

                # Slots füllen (wie bisher)
                match = re.match(r'^(\d+)', file)
                if match:
                    num = int(match.group(1))
                    if 1 <= num <= 128:
                        name_clean = os.path.splitext(file)[0]
                        display_name = name_clean[7:] if len(name_clean) > 7 else name_clean
                        slots[num-1] = display_name

        bank_type = "DreamDexed" if has_effects else "MiniDexed"

        # ---- Ordnername in Nummer und Namen zerlegen ----
        match = re.match(r'^0*(\d+)[\s\-_]+(.*)', bank_name)
        if match:
            bank_num = match.group(1)
            bank_name_clean = match.group(2)
        else:
            bank_num = "?"
            bank_name_clean = bank_name

        # ---- Titel dynamisch setzen ----
        if index == 0:
            display_bank = f"{bank_type} Performance List - Bank {bank_num}: {bank_name_clean}"
        else:
            display_bank = f"{bank_type} - Bank {bank_num}: {bank_name_clean}"

        elements.append(Paragraph(display_bank, title_style))

        # ---- Tabellenaufbau (unverändert) ----
        table_data = [["No.", "Performance Name", "No.", "Performance Name",
                       "No.", "Performance Name", "No.", "Performance Name"]]
        for i in range(32):
            row = []
            for col in range(4):
                idx = i + (col * 32)
                row.append(f"{idx+1:03d}")
                row.append(slots[idx])
            table_data.append(row)

        col_w = [10*mm, 59*mm, 10*mm, 59*mm, 10*mm, 59*mm, 10*mm, 59*mm]
        t = Table(table_data, colWidths=col_w)
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.black),
            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 8),
            ('GRID', (0,0), (-1,-1), 0.1, colors.grey),
            ('BACKGROUND', (0,1), (0,-1), colors.lightgrey),
            ('BACKGROUND', (2,1), (2,-1), colors.lightgrey),
            ('BACKGROUND', (4,1), (4,-1), colors.lightgrey),
            ('BACKGROUND', (6,1), (6,-1), colors.lightgrey),
            ('TOPPADDING', (0,0), (-1,-1), CELL_PADDING),
            ('BOTTOMPADDING', (0,0), (-1,-1), CELL_PADDING),
            ('TOPPADDING', (0,0), (-1,0), 6),
            ('BOTTOMPADDING', (0,0), (-1,0), 6),
        ]))
        elements.append(t)
        elements.append(PageBreak())

    # PDF bauen
    try:
        doc.build(elements[:-1], onFirstPage=lambda canvas, doc: draw_footer(canvas, doc, footer_text),
                                 onLaterPages=lambda canvas, doc: draw_footer(canvas, doc, footer_text))
        return True, f"PDF created: {pdf_filepath}"
    except Exception as e:
        return False, f"Error saving PDF: {e}"