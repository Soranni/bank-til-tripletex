"""Convert Nordea CSV bank statement to Tripletex Mamut GBAT10 format.

Uses ALL available data from the Nordea CSV:
- Header: account name, account number, period (Fra/Til)
- Transactions: date, amount, name, title, KID, payment type

Output: GBAT10 semicolon-separated file for Tripletex bilagsimport.
Each transaction -> 2 balanced lines (1920 Bank + 1909 motpost).
"""

import csv
import sys
import os
from datetime import datetime


def parse_header(f):
    """Parse Nordea CSV header to extract account info."""
    info = {
        'account_name': '',
        'account_number': '',
        'iban': '',
        'period_from': '',
        'period_to': '',
    }
    for line in f:
        line = line.strip()
        if line.startswith('Navn:'):
            parts = line.split(',')
            info['account_name'] = parts[1].strip() if len(parts) > 1 else ''
        elif line.startswith('Kontonummer:'):
            parts = line.split(',')
            info['account_number'] = parts[1].strip() if len(parts) > 1 else ''
            if len(parts) > 4:
                info['period_to'] = parts[4].strip()
        elif line.startswith('IBAN:'):
            parts = line.split(',')
            info['iban'] = parts[1].strip() if len(parts) > 1 else ''
            if len(parts) > 4:
                # "Dager:" field
                pass
        elif 'Fra:' in line:
            parts = line.split(',')
            for i, p in enumerate(parts):
                if 'Fra:' in p and i + 1 < len(parts):
                    info['period_from'] = parts[i + 1].strip()
        elif 'Bokf' in line and 'ringsdato' in line:
            break  # Column header found, stop parsing header
    return info


def parse_amount(utgaende, innkommende):
    """Parse Norwegian number format. Returns (amount_float, is_credit)."""
    if innkommende and innkommende.strip().replace('"', ''):
        val = innkommende.strip().replace('"', '').replace(',', '.').replace(' ', '')
        return abs(float(val)), True
    elif utgaende and utgaende.strip().replace('"', ''):
        val = utgaende.strip().replace('"', '').replace(',', '.').replace(' ', '').replace('-', '')
        return abs(float(val)), False
    return 0, True


def build_description(navn, tittel, kid, betalingstype):
    """Build a rich description from all available fields."""
    # Primary: name of counterpart
    primary = ''
    if navn:
        primary = navn
    elif tittel:
        primary = tittel

    # Payment type as context
    ptype = betalingstype or ''

    # Build description
    parts = []
    if primary:
        parts.append(primary)
    if ptype and ptype.lower() != primary.lower():
        parts.append(f'({ptype})')
    if kid:
        parts.append(f'KID:{kid}')

    desc = ' '.join(parts) if parts else 'Banktransaksjon'
    return desc[:100]  # Max 100 chars for GBAT10


def gbat10_line(voucher_num, date_yyyymmdd, period, year, account, amount, description,
                bank_account=''):
    """Build one GBAT10 line matching Tripletex format (28 columns)."""
    cols = [
        'GBAT10',                    # 1:  Identification
        str(voucher_num),            # 2:  Voucher number
        date_yyyymmdd,               # 3:  Voucher date
        '1',                         # 4:  Voucher type
        str(period),                 # 5:  Period (ignored by TT but good practice)
        str(year),                   # 6:  Accounting year (ignored by TT)
        str(account),                # 7:  Account number
        '1',                         # 8:  VAT code (1 = no VAT)
        f'{amount:.2f}',             # 9:  Net amount
        '0',                         # 10: Customer number
        '0',                         # 11: Supplier number
        '',                          # 12: Contact name
        '',                          # 13: Address
        '',                          # 14: Postal number
        '',                          # 15: City
        '',                          # 16: Invoice number (ignored)
        '',                          # 17: KID (ignored)
        '',                          # 18: Due date (ignored)
        '0',                         # 19: (unused)
        bank_account,                # 20: Bank account
        description,                 # 21: Ledger description
        description,                 # 22: Sub-ledger description
        '1',                         # 23: Interest invoicing
        '0',                         # 24: Project
        '0',                         # 25: Department
        '0',                         # 26: Payment terms
        'T',                         # 27: Gross amount type
        f'{amount:.2f}',             # 28: Gross amount
    ]
    return ';'.join(cols)


def detect_format(input_file):
    """Detect bank CSV format. Returns 'nordea', 'oversiktkonti', 'kontoinfo' or 'transaksjonsliste'."""
    # Prøv ISO-8859-1 først (sparebank1/eika bruker det)
    try:
        with open(input_file, 'r', encoding='iso-8859-1') as f:
            first_lines = [f.readline().strip() for _ in range(8)]
    except Exception:
        first_lines = []

    head_blob = '\n'.join(first_lines)
    # Sparebank1/Eika "kontoinfo": semikolon, har "Konto";"Kontonavn" og "Bokført dato"
    if '"Konto"' in head_blob and ('Bokført dato' in head_blob or 'Bokf\xf8rt dato' in head_blob):
        return 'kontoinfo'

    # DNB/Sbanken / Handelsbanken: starter med "Dato;..."
    with open(input_file, 'r', encoding='utf-8-sig') as f:
        first = f.readline().strip()
    # Handelsbanken Transaksjonsliste: "Dato;Type;Antall;Konto;Inn;Ut;Valuta;Beskrivelse;..."
    if first.startswith('Dato;Type;') and 'Beskrivelse' in first:
        return 'transaksjonsliste'
    # DNB/Sbanken "OversiktKonti". Banken har byttet kolonnenavn over tid:
    # 2025-eksporten sier "Beskrivelse", 2026-eksporten sier "Omtale".
    # Krev derfor bare Dato + Inn + Ut, ikke et bestemt tekstkolonnenavn.
    if first.startswith('Dato;') and 'Inn' in first and 'Ut' in first:
        return 'oversiktkonti'
    return 'nordea'


def parse_transaksjonsliste(input_file):
    """Parse Handelsbanken 'Transaksjonsliste' CSV (semicolon, DD.MM.YYYY)."""
    transactions = []
    own_account = ''
    with open(input_file, 'r', encoding='utf-8-sig') as f:
        reader = csv.reader(f, delimiter=';')
        next(reader, None)  # header
        for row in reader:
            if not row or not row[0].strip():
                continue
            date_str = row[0].strip()
            # cols: 0=Dato, 1=Type, 2=Antall, 3=Konto, 4=Inn, 5=Ut, 6=Valuta, 7=Beskrivelse
            konto = (row[3] if len(row) > 3 else '').strip()
            inn = (row[4] if len(row) > 4 else '').strip()
            ut = (row[5] if len(row) > 5 else '').strip()
            beskrivelse = (row[7] if len(row) > 7 else '').strip().strip('"')

            try:
                dt = datetime.strptime(date_str, '%d.%m.%Y')
            except Exception:
                continue
            if not own_account and konto:
                own_account = konto

            if inn:
                try:
                    amount = abs(float(inn.replace(' ', '').replace(',', '.')))
                except Exception:
                    continue
                is_credit = True
            elif ut:
                try:
                    amount = abs(float(ut.replace(' ', '').replace(',', '.')))
                except Exception:
                    continue
                is_credit = False
            else:
                continue
            if amount == 0:
                continue

            desc = (beskrivelse or 'Banktransaksjon')[:100]
            transactions.append({
                'date': dt.strftime('%Y%m%d'),
                'period': dt.month,
                'year': dt.year,
                'amount': amount,
                'is_credit': is_credit,
                'desc': desc,
            })
    header = {
        'account_name': '',
        'account_number': own_account,
        'period_from': min((t['date'] for t in transactions), default=''),
        'period_to': max((t['date'] for t in transactions), default=''),
    }
    return header, transactions


def parse_kontoinfo(input_file):
    """Parse Sparebank1/Eika 'kontoinfo' (ISO-8859-1, semicolon, header-blokker)."""
    transactions = []
    own_account = ''
    account_name = ''
    with open(input_file, 'r', encoding='iso-8859-1') as f:
        reader = csv.reader(f, delimiter=';', quotechar='"')
        header_seen = False
        for row in reader:
            if not row:
                continue
            first = row[0].strip()
            # Plukk opp kontoinfo fra blokk-headerne
            if first == 'Konto':
                continue  # neste rad har verdiene
            if not own_account and first and first.replace('.', '').isdigit() and '.' in first:
                # Konto-rad: "1234.56.78901";"DEMO VERKSTED AS"
                own_account = first.replace('.', '')
                account_name = (row[1].strip() if len(row) > 1 else '')
                continue
            if first in ('Inngående saldo', 'Inng\xe5ende saldo'):
                continue  # neste rad er saldotall
            # Dataregisteret begynner ved "Bokført dato"-headeren
            if 'Bokf' in first and ('rt dato' in first or 'rt Dato' in first):
                header_seen = True
                continue
            if not header_seen:
                continue
            if len(row) < 7:
                continue

            date_str = first
            forklaring = (row[1] if len(row) > 1 else '').strip()
            ut = (row[5] if len(row) > 5 else '').strip()
            inn = (row[6] if len(row) > 6 else '').strip()

            try:
                dt = datetime.strptime(date_str, '%d.%m.%Y')
            except Exception:
                continue

            def parse_no_num(s):
                """1.234,56 → 1234.56  /  -1.234,56 → -1234.56"""
                s = s.replace(' ', '').replace('.', '').replace(',', '.')
                return float(s)

            if inn:
                try:
                    amount = abs(parse_no_num(inn))
                except Exception:
                    continue
                is_credit = True
            elif ut:
                try:
                    amount = abs(parse_no_num(ut))
                except Exception:
                    continue
                is_credit = False
            else:
                continue
            if amount == 0:
                continue

            desc = (forklaring or 'Banktransaksjon')[:100]
            transactions.append({
                'date': dt.strftime('%Y%m%d'),
                'period': dt.month,
                'year': dt.year,
                'amount': amount,
                'is_credit': is_credit,
                'desc': desc,
            })
    header = {
        'account_name': account_name,
        'account_number': own_account,
        'period_from': min((t['date'] for t in transactions), default=''),
        'period_to': max((t['date'] for t in transactions), default=''),
    }
    return header, transactions


def parse_oversiktkonti(input_file):
    """Parse DNB/Sbanken 'OversiktKonti' CSV (semicolon, DD.MM.YYYY, Inn/Ut)."""
    transactions = []
    own_account = ''
    with open(input_file, 'r', encoding='utf-8-sig') as f:
        reader = csv.reader(f, delimiter=';')
        header_row = next(reader, None) or []

        # Finn kolonnene på navn. Banken har endret både navn ("Beskrivelse"
        # -> "Omtale") og rekkefølge mellom eksportene, så faste indekser
        # ryker ved neste endring. Faller tilbake på gammel posisjon hvis
        # navnet ikke kjennes igjen.
        names = [c.strip().strip('"').lower() for c in header_row]

        def col(candidates, fallback):
            for cand in candidates:
                if cand in names:
                    return names.index(cand)
            return fallback

        i_dato = col(['dato'], 0)
        i_tekst = col(['omtale', 'beskrivelse', 'tekst'], 1)
        i_inn = col(['inn', 'innkommende'], 3)
        i_ut = col(['ut', 'utgaende', 'utgående'], 4)
        i_til = col(['til konto', 'til'], 5)
        i_fra = col(['fra konto', 'fra'], 6)

        def cell(row, idx):
            return (row[idx] if 0 <= idx < len(row) else '').strip().strip('"')

        for row in reader:
            if not row or not row[0].strip():
                continue
            date_str = cell(row, i_dato)
            beskrivelse = cell(row, i_tekst)
            inn = cell(row, i_inn)
            ut = cell(row, i_ut)
            til_konto = cell(row, i_til)
            fra_konto = cell(row, i_fra)

            try:
                dt = datetime.strptime(date_str, '%d.%m.%Y')
            except Exception:
                continue

            if inn:
                amount = abs(float(inn.replace(',', '.').replace(' ', '')))
                is_credit = True
                if not own_account:
                    own_account = til_konto
            elif ut:
                amount = abs(float(ut.replace(',', '.').replace(' ', '').replace('-', '')))
                is_credit = False
                if not own_account:
                    own_account = fra_konto
            else:
                continue
            if amount == 0:
                continue

            desc = (beskrivelse or 'Banktransaksjon')[:100]
            transactions.append({
                'date': dt.strftime('%Y%m%d'),
                'period': dt.month,
                'year': dt.year,
                'amount': amount,
                'is_credit': is_credit,
                'desc': desc,
            })
    header = {
        'account_name': '',
        'account_number': own_account,
        'period_from': min((t['date'] for t in transactions), default=''),
        'period_to': max((t['date'] for t in transactions), default=''),
    }
    return header, transactions


def parse_nordea(input_file):
    """Parse Nordea CSV (comma-separated, YYYY/MM/DD, with account header)."""
    with open(input_file, 'r', encoding='utf-8-sig') as f:
        header = parse_header(f)
        reader = csv.reader(f)
        transactions = []
        for row in reader:
            if not row or not row[0].strip() or row[0].startswith('Sum') or row[0].startswith('Total'):
                continue

            date_str = row[0].strip()
            utgaende = row[1] if len(row) > 1 else ''
            innkommende = row[2] if len(row) > 2 else ''
            navn = (row[5] if len(row) > 5 else '').strip()
            tittel = (row[6] if len(row) > 6 else '').strip()
            kid = (row[7] if len(row) > 7 else '').strip()
            betalingstype = (row[9] if len(row) > 9 else '').strip()

            amount, is_credit = parse_amount(utgaende, innkommende)
            if amount == 0:
                continue

            try:
                dt = datetime.strptime(date_str, '%Y/%m/%d')
            except Exception:
                continue

            desc = build_description(navn, tittel, kid, betalingstype)
            transactions.append({
                'date': dt.strftime('%Y%m%d'),
                'period': dt.month,
                'year': dt.year,
                'amount': amount,
                'is_credit': is_credit,
                'desc': desc,
            })
    return header, transactions


def convert_nordea_to_gbat10(input_file, output_file):
    """Convert bank CSV to GBAT10. Auto-detects Nordea or OversiktKonti format."""

    BANK_ACCOUNT = 1920
    COUNTER_ACCOUNT = 1909

    fmt = detect_format(input_file)
    if fmt == 'oversiktkonti':
        header, transactions = parse_oversiktkonti(input_file)
    elif fmt == 'kontoinfo':
        header, transactions = parse_kontoinfo(input_file)
    elif fmt == 'transaksjonsliste':
        header, transactions = parse_transaksjonsliste(input_file)
    else:
        header, transactions = parse_nordea(input_file)

    if not transactions:
        print("Ingen transaksjoner funnet!")
        return

    # Bank account number for reference (field 20)
    bank_acct = header.get('account_number', '')

    # Generate GBAT10 lines
    lines = []
    for i, t in enumerate(transactions):
        vn = i + 1

        if t['is_credit']:
            lines.append(gbat10_line(vn, t['date'], t['period'], t['year'],
                                     BANK_ACCOUNT, t['amount'], t['desc'], bank_acct))
            lines.append(gbat10_line(vn, t['date'], t['period'], t['year'],
                                     COUNTER_ACCOUNT, -t['amount'], t['desc']))
        else:
            lines.append(gbat10_line(vn, t['date'], t['period'], t['year'],
                                     BANK_ACCOUNT, -t['amount'], t['desc'], bank_acct))
            lines.append(gbat10_line(vn, t['date'], t['period'], t['year'],
                                     COUNTER_ACCOUNT, t['amount'], t['desc']))

    # Write ISO-8859-1 (Tripletex standard)
    with open(output_file, 'w', encoding='iso-8859-1') as f:
        for line in lines:
            f.write(line + '\n')

    total_in = sum(t['amount'] for t in transactions if t['is_credit'])
    total_out = sum(t['amount'] for t in transactions if not t['is_credit'])

    print(f"Konvertert: {os.path.basename(input_file)}")
    print(f"  Konto: {header.get('account_name', '?')} ({header.get('account_number', '?')})")
    print(f"  Periode: {header.get('period_from', '?')} - {header.get('period_to', '?')}")
    print(f"  Transaksjoner: {len(transactions)} -> {len(lines)} GBAT10-linjer")
    print(f"  Innkommende: {total_in:,.2f} kr")
    print(f"  Utgaende:    {total_out:,.2f} kr")
    print(f"  Netto:       {total_in - total_out:,.2f} kr")
    print(f"  Output:      {output_file}")
    print(f"\nImporter i Tripletex:")
    print(f"  Filtype: Mamut GBAT10")
    print(f"  Tegnsett: ISO-8859-1")
    print(f"  Huk av: La Tripletex generere mva-posteringene")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Bruk: python3 convert_to_gbat10.py <bankfil.csv> [ut.csv]')
        sys.exit(1)
    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else 'banktransaksjoner_gbat10.csv'
    convert_nordea_to_gbat10(input_file, output_file)
