"""Lager syntetiske testfiler for bank-til-tripletex.

Alle data her er oppdiktet. Ekte bankutskrifter skal ALDRI ligge i dette
repoet - de hører hjemme i bankdata/ utenfor git.

Kjør:  python3 lag-testfiler.py
"""

import os

UT = 'testfiler'

KONTO = '1234.56.78901'
FIRMA = 'DEMO VERKSTED AS'
INNGAAENDE = 10000.00

# (dato, tekst, transaksjonstype, belop)  -  positivt = inn, negativt = ut
POSTER = [
    ('03.08.2026', 'Strøm Øst AS',            'Giro',                -2450.00),
    ('03.08.2026', 'Dekk & Felg Engros',      'Overføring innland',  -8900.50),
    ('04.08.2026', 'Kari Nordmann',           'Overføring innland',  12500.00),
    ('05.08.2026', 'Forsikring Nord',         'Giro',                -1330.49),
    ('06.08.2026', 'Ola Hansen',              'Giro',                 4375.00),
    ('10.08.2026', 'Verktøy Sør AS',          'Visa',                -3199.00),
    ('12.08.2026', 'Åse Bjørnstad',           'Overføring innland',   7800.00),
    ('14.08.2026', 'Telenor Norge',           'Giro',                 -786.76),
    ('18.08.2026', 'Ærlig Regnskap AS',       'Giro',                -4375.00),
    ('20.08.2026', 'Kontantsalg uke 34',      'Innskudd',            15250.25),
    ('25.08.2026', 'Øvre Bilrekvisita',       'Visa',                -1499.00),
    ('31.08.2026', 'Renter',                  'Renter',                 42.10),
]


def no(x):
    """1234.56 -> '1.234,56' (norsk tallformat)."""
    s = '{:,.2f}'.format(abs(x)).replace(',', '\x00').replace('.', ',').replace('\x00', '.')
    return ('-' if x < 0 else '') + s


def q(*celler):
    return ';'.join('"{}"'.format(c) for c in celler)


def bygg(poster, dato_kolonne='Bokført dato'):
    sum_inn = sum(p[3] for p in poster if p[3] > 0)
    sum_ut = sum(-p[3] for p in poster if p[3] < 0)
    utgaaende = INNGAAENDE + sum_inn - sum_ut

    linjer = [
        q('Konto', 'Kontonavn'),
        q(KONTO, FIRMA),
        q('Inngående saldo', 'Utgående saldo', 'Sum inn på konto', 'Sum ut av konto'),
        q(no(INNGAAENDE), no(utgaaende), no(sum_inn), no(-sum_ut)),
        q(dato_kolonne, 'Forklarende tekst', 'Status', 'Transaksjonstype',
          'Rentedato', 'Ut', 'Inn', 'Arkivref.', 'Referanse'),
    ]
    for i, (dato, tekst, ttype, belop) in enumerate(poster):
        ut = no(belop) if belop < 0 else ''
        inn = no(belop) if belop > 0 else ''
        linjer.append(q(dato, tekst, 'B', ttype, dato, ut, inn,
                        str(800000000 + i), str(3000000 + i)))
    return '\n'.join(linjer) + '\n'


def skriv(navn, innhold, encoding='iso-8859-1'):
    sti = os.path.join(UT, navn)
    with open(sti, 'w', encoding=encoding) as f:
        f.write(innhold)
    print('  {:38s} {:>6} byte'.format(navn, os.path.getsize(sti)))


os.makedirs(UT, exist_ok=True)
print('Lager testfiler i {}/:'.format(UT))

gyldig = bygg(POSTER)
skriv('demo-sparebank1-gyldig.csv', gyldig)

# 1: bank vi ikke støtter i det hele tatt
skriv('test-1-ukjent-bank.csv',
      'Date,Description,Debit,Credit,Balance\n'
      '2026-08-03,Power Supplier Ltd,2450.00,,7550.00\n'
      '2026-08-04,Jane Doe,,12500.00,20050.00\n',
      encoding='utf-8')

# 2: riktig bank, men banken eksporterte null transaksjoner
skriv('test-2-ingen-transaksjoner.csv', bygg([]))

# 3: lagret på nytt i Excel på norsk oppsett - semikolon beholdes, men
#    anførselstegn forsvinner og tegnsettet blir UTF-8. Skal fortsatt leses.
excel_semi = gyldig.replace('"', '')
skriv('test-3-excel-lagret.csv', excel_semi, encoding='utf-8-sig')

# 7: lagret med komma som skilletegn - kolliderer med desimalkommaet i
#    beløpene, og lar seg ikke redde. Skal gi en egen forklaring.
excel_komma = '\n'.join(','.join(c.strip('"') for c in linje.split('";"'))
                        for linje in gyldig.strip().split('\n'))
skriv('test-7-excel-komma.csv', excel_komma.replace('"', '') + '\n', encoding='utf-8-sig')

# 4: banken har døpt om datokolonnen
skriv('test-4-nytt-kolonnenavn.csv', bygg(POSTER, dato_kolonne='Bokføringsdato'))

# 5: én transaksjon lest med feil beløp -> summen matcher ikke bankens sluttsummer
feil = list(POSTER)
feil[2] = (feil[2][0], feil[2][1], feil[2][2], 1250.00)   # 12.500,00 -> 1.250,00
skriv('test-5-avvik-i-sum.csv',
      bygg(POSTER).split(q('Bokført dato'))[0] + q(
          'Bokført dato', 'Forklarende tekst', 'Status', 'Transaksjonstype',
          'Rentedato', 'Ut', 'Inn', 'Arkivref.', 'Referanse') + '\n' +
      '\n'.join(bygg(feil).split('\n')[5:]).lstrip('\n'))

# 6: linjer med dato, men uten lesbart beløp (reservert kortkjøp o.l.)
uleselig = gyldig.rstrip('\n') + '\n' + '\n'.join([
    q('15.08.2026', 'Reservert kortkjøp', 'R', 'Visa', '15.08.2026', '', '', '800009999', '9999'),
    q('16.08.2026', 'Ugyldig beløp', 'B', 'Giro', '16.08.2026', 'xx,yy', '', '800009998', '9998'),
]) + '\n'
skriv('test-6-uleselige-linjer.csv', uleselig)

print('\nFerdig. Alle data er oppdiktet.')
