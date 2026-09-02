from __future__ import annotations

import argparse
import json
from pathlib import Path

from reportlab.lib.colors import HexColor, white
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

W, H = A4
NAVY = HexColor('#0b3767')
PALE = HexColor('#edf3fa')
BORDER = HexColor('#cbd8e6')
TEXT = HexColor('#102d50')
GREEN = HexColor('#159447')
ORANGE = HexColor('#f39200')
RED = HexColor('#c83d4b')
GRAY = HexColor('#6f7f91')
LGRAY = HexColor('#f3f6fa')
M = 22


def txt(c, x, y, s, size=8, bold=False, color=TEXT, align='left'):
    c.setFillColor(color)
    c.setFont('Helvetica-Bold' if bold else 'Helvetica', size)
    s = str(s)
    if align == 'center':
        c.drawCentredString(x, y, s)
    elif align == 'right':
        c.drawRightString(x, y, s)
    else:
        c.drawString(x, y, s)


def wrap(c, text, x, y, width, size=8, leading=10, bold=False, color=TEXT, max_lines=None):
    words = str(text).split()
    lines, line = [], ''
    font = 'Helvetica-Bold' if bold else 'Helvetica'
    for word in words:
        trial = (line + ' ' + word).strip()
        if stringWidth(trial, font, size) <= width:
            line = trial
        else:
            if line:
                lines.append(line)
            line = word
    if line:
        lines.append(line)
    if max_lines:
        lines = lines[:max_lines]
    for i, ln in enumerate(lines):
        txt(c, x, y - i * leading, ln, size, bold, color)
    return y - len(lines) * leading


def rounded(c, x, y, w, h, fill=white, stroke=BORDER, r=7, lw=.8):
    c.setLineWidth(lw)
    c.setStrokeColor(stroke)
    c.setFillColor(fill)
    c.roundRect(x, y, w, h, r, fill=1, stroke=1)


def header(c, page, title, status):
    c.setFillColor(NAVY)
    c.rect(0, H - 26, W, 26, fill=1, stroke=0)
    txt(c, M, H - 17, status, 6.5, True, white)
    txt(c, W - M, H - 17, f'Pagina {page} van 13', 6.5, True, white, 'right')
    txt(c, M, H - 52, title, 16, True, TEXT)


def footer(c):
    txt(c, W - 18, 12, 'Energierapport', 5, False, GRAY, 'right')


def table(c, x, y, w, headers, rows, col_fracs=None, row_h=28, font=7):
    n = len(headers)
    col_fracs = col_fracs or [1 / n] * n
    widths = [w * f for f in col_fracs]
    c.setFillColor(NAVY)
    c.rect(x, y - row_h, w, row_h, fill=1, stroke=0)
    cx = x
    for i, heading in enumerate(headers):
        txt(c, cx + 8, y - row_h + 9, heading, font, True, white)
        cx += widths[i]
    yy = y - row_h
    for r, row in enumerate(rows):
        yy -= row_h
        c.setFillColor(LGRAY if r % 2 else white)
        c.rect(x, yy, w, row_h, fill=1, stroke=0)
        cx = x
        for i, value in enumerate(row):
            wrap(c, str(value), cx + 8, yy + row_h - 11, widths[i] - 12, font, 8, max_lines=2)
            cx += widths[i]
    return yy


def callout(c, x, y, w, h, title, body, kind='info'):
    fill = PALE if kind == 'info' else HexColor('#fff7e7')
    stroke = HexColor('#9cb9d6') if kind == 'info' else ORANGE
    rounded(c, x, y, w, h, fill, stroke, 7)
    c.setFillColor(NAVY if kind == 'info' else ORANGE)
    c.circle(x + 18, y + h - 21, 12, fill=1, stroke=0)
    txt(c, x + 18, y + h - 24, 'i' if kind == 'info' else '!', 9, True, white, 'center')
    txt(c, x + 40, y + h - 22, title, 8, True, TEXT if kind == 'info' else ORANGE)
    wrap(c, body, x + 40, y + h - 38, w - 52, 7.2, 9)


def kpi_card(c, x, y, w, h, value, label, sub):
    rounded(c, x, y, w, h)
    txt(c, x + w / 2, y + h - 30, value, 14, True, TEXT, 'center')
    txt(c, x + w / 2, y + h - 63, label, 7, True, TEXT, 'center')
    txt(c, x + w / 2, y + 10, sub, 6, False, GRAY, 'center')


def fmt_num(value, unit='', decimals=1):
    if not isinstance(value, (int, float)):
        return 'n.b.'
    text = f'{value:.{decimals}f}'.replace('.', ',')
    return f'{text} {unit}'.strip()


def page3(c, d):
    header(c, 3, f"2. Dashboard - {d['meta']['month']}", d['meta']['status'])
    dash = d['dashboard']
    vals = [
        (fmt_num(dash.get('house'), 'kWh'), 'Totaal huisverbruik', 'alleen bij complete PV-balans'),
        (fmt_num(dash.get('solar'), 'kWh'), 'Gemeten Enphase-productie', 'gemeten PV-bron'),
        (fmt_num(dash.get('self'), '%'), 'Zelfconsumptie', 'niet schatten bij bronverschil'),
        (fmt_num(dash.get('export'), 'kWh'), 'Netto teruglevering', 'P1 gemeten'),
    ]
    gap = 12
    cw = (W - 2 * M - 3 * gap) / 4
    for i, val in enumerate(vals):
        kpi_card(c, M + i * (cw + gap), H - 175, cw, 78, *val)
    rounded(c, M, H - 285, W - 2 * M, 88)
    txt(c, M + 20, H - 220, 'Energiescore', 8, True)
    txt(c, W / 2, H - 260, 'n.b.', 18, True, ORANGE, 'center')
    txt(c, W / 2, H - 282, dash.get('quality', 'Bronstatus onbekend'), 7, True, TEXT, 'center')
    rows = [
        ['Netafname', fmt_num(d['electricity'].get('grid'), 'kWh'), 'Gemeten', 'P1'],
        ['Teruglevering', fmt_num(d['electricity'].get('feedin'), 'kWh'), 'Gemeten', 'P1'],
        ['Gas', fmt_num(d['gas'].get('month'), 'm³'), 'Gemeten', 'P1g'],
        ['PV-productie', fmt_num(d['solar'].get('production'), 'kWh'), 'Gemeten bron', d['solar'].get('source', 'Enphase')],
        ['Zelfconsumptie', fmt_num(d['solar'].get('self'), '%'), 'Bronbeperkt' if not d['solar'].get('reliable') else 'Beschikbaar', 'Geen nul-fallback'],
        ['Financieel', '€ 1.836/jaar', 'Offerteprognose', 'NextEnergy'],
    ]
    table(c, M, H - 320, W - 2 * M, ['Onderdeel', 'Waarde', 'Status', 'Bron / regel'], rows, [.28, .20, .20, .32], 38, 7)
    callout(c, M, 50, W - 2 * M, 88, 'Leeswijzer', 'Deze pagina toont alleen gemeten waarden en expliciet gemarkeerde afgeleide waarden. Een ontbrekende of inconsistente bron wordt niet vervangen door een fictieve nul of demo-waarde.')
    footer(c)


def page4(c, d):
    header(c, 4, '3. Meetbasis en bronafbakening', d['meta']['status'])
    wrap(c, 'De rapportage gebruikt de bronwaarden van de gekozen rapportmaand. Afgeleide zonne-KPI’s worden alleen berekend wanneer productie en netteruglevering dezelfde totale meetdekking vertegenwoordigen.', M, H - 90, W - 2 * M, 8.3, 11, True)
    solar = d['solar']
    rows = [
        ['Netafname', fmt_num(d['electricity'].get('grid'), 'kWh'), 'P1'],
        ['Teruglevering', fmt_num(d['electricity'].get('feedin'), 'kWh'), 'P1'],
        ['Gas', fmt_num(d['gas'].get('month'), 'm³'), 'P1g'],
        ['Enphase-productie', fmt_num(solar.get('production'), 'kWh'), solar.get('source', 'Enphase')],
        ['Direct eigen gebruik', fmt_num(solar.get('direct'), 'kWh'), 'Alleen bij consistente totale PV-dekking'],
        ['Totaal huishoudelijk gebruik', fmt_num(d['electricity'].get('house'), 'kWh'), 'Alleen bij consistente totale PV-dekking'],
        ['Rapportmaand-contract', d['finance'].get('contract_label', 'NextEnergy'), 'Contract actief in rapportmaand'],
    ]
    table(c, M, H - 145, W - 2 * M, ['Waarde', 'Maanddata', 'Herkomst / regel'], rows, [.34, .24, .42], 42, 7.7)
    limitation = solar.get('limitation') or 'PV-balans consistent; afgeleide zonne-KPI’s zijn berekend.'
    callout(c, M, 85, W - 2 * M, 110, 'PV-broncontrole', limitation, 'warn' if not solar.get('reliable') else 'info')
    footer(c)


def page5(c, d):
    header(c, 5, '4. Elektriciteitsanalyse', d['meta']['status'])
    e = d['electricity']
    net = e.get('net')
    direction = 'netto teruglevering' if isinstance(net, (int, float)) and net < 0 else 'netto afname'
    wrap(c, f"In {d['meta']['month']} bedraagt de gemeten netafname {fmt_num(e.get('grid'),'kWh')} en de gemeten teruglevering {fmt_num(e.get('feedin'),'kWh')}. De netpositie is {fmt_num(abs(net) if isinstance(net,(int,float)) else None,'kWh')} {direction}.", M, H - 90, W - 2 * M, 8.3, 11, True)
    rows = [
        ['Netafname', fmt_num(e.get('grid'), 'kWh'), 'Gemeten'],
        ['Teruglevering', fmt_num(e.get('feedin'), 'kWh'), 'Gemeten'],
        ['Netto netpositie', fmt_num(e.get('net'), 'kWh'), direction],
        ['Gemiddelde netafname per kalenderdag', fmt_num(e.get('grid_day'), 'kWh'), 'Rekenkundig uit maandtotaal'],
        ['Gemiddelde teruglevering per kalenderdag', fmt_num(e.get('feedin_day'), 'kWh'), 'Rekenkundig uit maandtotaal'],
        ['Totaal huisverbruik', fmt_num(e.get('house'), 'kWh'), 'Alleen bij betrouwbare PV-balans'],
    ]
    table(c, M, H - 150, W - 2 * M, ['KPI', 'Waarde', 'Beoordeling'], rows, [.42, .22, .36], 45, 8)
    callout(c, M, 70, W - 2 * M, 105, 'Dagprofiel', 'Er wordt geen verzonnen dagcurve getoond. Een daggrafiek verschijnt pas wanneer de rapportadapter een echte, gevalideerde dag- of kwartierreeks aanlevert.')
    footer(c)


def page6(c, d):
    header(c, 6, '5. Zonnepanelen en zelfconsumptie', d['meta']['status'])
    s = d['solar']
    rows = [
        ['Gemeten Enphase-productie', fmt_num(s.get('production'), 'kWh'), s.get('source', 'Enphase')],
        ['P1-teruglevering', fmt_num(s.get('feedin'), 'kWh'), 'P1'],
        ['Direct eigen gebruik', fmt_num(s.get('direct'), 'kWh'), 'Alleen bij consistente totale PV-dekking'],
        ['Zelfconsumptie', fmt_num(s.get('self'), '%'), 'Geen 0%-fallback'],
        ['Directe zonnedekking woning', fmt_num(s.get('coverage'), '%'), 'Geen 0%-fallback'],
    ]
    table(c, M, H - 105, W - 2 * M, ['Indicator', 'Waarde', 'Interpretatie'], rows, [.38, .22, .40], 50, 8)
    if s.get('reliable'):
        body = 'De productie- en terugleveringsbronnen zijn voor dezelfde dekking consistent; zelfconsumptie kan daardoor worden berekend.'
        kind = 'info'
    else:
        body = s.get('limitation') or 'De PV-bronnen zijn niet voldoende gelijksoortig om zelfconsumptie betrouwbaar te berekenen.'
        kind = 'warn'
    callout(c, M, 125, W - 2 * M, 120, 'Bronbeperking', body, kind)
    callout(c, M, 40, W - 2 * M, 70, 'Praktische optimalisatie', 'Flexibele verbruikers kunnen naar zonnige uren worden verschoven, maar het rapport kwantificeert het effect pas wanneer totale PV-productie en P1-teruglevering dezelfde dekking hebben.')
    footer(c)


def page7(c, d):
    header(c, 7, '6. Apparaten, airco en heaters', d['meta']['status'])
    table(c, M, H - 92, W - 2 * M, ['Apparaat', 'kWh', 'Status', 'Bron'], d['appliances']['rows'], [.34, .14, .20, .32], 43, 7.7)
    callout(c, M, 70, W - 2 * M, 105, 'Toelichting', d['appliances']['note'])
    footer(c)


def page8(c, d):
    header(c, 8, '7. Gasanalyse', d['meta']['status'])
    g = d['gas']
    vals = [
        (fmt_num(g.get('month'), 'm³'), 'Gas rapportmaand', 'gemeten maandtotaal'),
        (fmt_num(g.get('per_day'), 'm³'), 'Per dag', 'alleen bij gevalideerde dagdekking'),
        (fmt_num(g.get('reference'), 'm³', 0), 'Jaarreferentie', 'officiële eindafrekening 2025-2026'),
    ]
    cw = (W - 2 * M - 20) / 3
    for i, val in enumerate(vals):
        kpi_card(c, M + i * (cw + 10), H - 180, cw, 85, *val)
    callout(c, M, 330, W - 2 * M, 115, 'Dekking', g.get('coverage_note', 'Daggemiddelde niet gebruikt zonder afzonderlijk gevalideerde dekking.'), 'warn')
    rows = [
        ['Rapportmaand', fmt_num(g.get('month'), 'm³'), 'Gemeten'],
        ['Jaarreferentie', fmt_num(g.get('reference'), 'm³', 0), 'Officieel 2025-2026'],
        ['Weerscorrectie', 'niet toegepast', 'Geen gevalideerde graaddagenbron'],
    ]
    table(c, M, 290, W - 2 * M, ['Vergelijking', 'Waarde', 'Status'], rows, [.34, .24, .42], 46, 8)
    callout(c, M, 65, W - 2 * M, 90, 'Conclusie', 'Het maandtotaal wordt gerapporteerd. Het rapport trekt geen weersconclusie en berekent geen daggemiddelde zolang de daarvoor benodigde brondekking niet afzonderlijk is gevalideerd.')
    footer(c)


def page9(c, d):
    header(c, 9, '8. Financiën en leverancierscontrole', d['meta']['status'])
    wrap(c, 'Bekende, bevestigde NextEnergy-offertewaarden worden expliciet getoond. Werkelijke augustus all-in kosten worden niet uit marktprijzen of termijnbedragen afgeleid.', M, H - 90, W - 2 * M, 8.3, 11, True)
    table(c, M, H - 145, W - 2 * M, ['Post', 'Basis', 'Bedrag / status'], d['finance']['rows'], [.34, .38, .28], 43, 7.6)
    cw = (W - 2 * M - 20) / 3
    cards = [
        ('€ 150,00', 'Huidige maandtermijn', 'bevestigd'),
        ('€ 153,00', 'Offerteprognose', 'per maand vanaf 3 sep'),
        ('€ 1.836,00', 'Verwachte jaarkosten', d['finance'].get('source', 'NextEnergy')),
    ]
    for i, val in enumerate(cards):
        kpi_card(c, M + i * (cw + 10), 205, cw, 85, *val)
    callout(c, M, 75, W - 2 * M, 100, 'Belangrijk', '€ 1.836 is de NextEnergy-offerteprognose (12 × €153). De verwachte betalingen bij een termijn van €150 zijn €1.800; het verschil is €36. Dit is geen berekende augustusfactuur.')
    footer(c)


def page10(c, d):
    header(c, 10, '9. Jaarprognose en contracthistorie', d['meta']['status'])
    wrap(c, d['forecast']['source'], M, H - 90, W - 2 * M, 8.3, 11, True)
    table(c, M, H - 135, W - 2 * M, ['Jaar-KPI', 'Referentie 2025-2026', 'Offerteprofiel', 'Verschil / bron'], d['forecast']['rows'], [.28, .24, .24, .24], 40, 7.3)
    hist_rows = []
    for row in d['forecast'].get('contract_years', []):
        if len(row) < 6:
            continue
        period, imp, exp, net, gas, quality = row[:6]
        hist_rows.append([period, fmt_num(imp, 'kWh', 0), fmt_num(exp, 'kWh', 0), fmt_num(gas, 'm³', 0), quality])
    txt(c, M, H - 390, 'Historische contractjaren', 10, True)
    table(c, M, H - 405, W - 2 * M, ['Periode', 'Verbruik', 'Teruglevering', 'Gas', 'Kwaliteit'], hist_rows, [.28, .18, .20, .16, .18], 42, 6.5)
    callout(c, M, 45, W - 2 * M, 78, 'Interpretatie', 'De offerteprognose gebruikt het profiel dat bij de NextEnergy-aanbieding is vastgelegd. Historische contractjaren worden uit de projecthistorie gelezen en niet uit de rapportfixture.')
    footer(c)


def page11(c, d):
    header(c, 11, '10. Thuisbatterij - één modelbasis', d['meta']['status'])
    b = d['battery']
    wrap(c, 'Alle batterijvermeldingen in dit rapport gebruiken dezelfde modelbasis. De bedragen zijn indicatieve modelwaarden en geen gemeten besparing.', M, H - 90, W - 2 * M, 8.3, 11, True)
    table(c, M, H - 140, W - 2 * M, ['Scenario', 'Configuratie', 'Verschuifbaar', 'Jaarwaarde', 'Oordeel'], b['rows'], [.16, .28, .16, .20, .20], 50, 7)
    rows = [
        ['Kandidaat', b['candidate']],
        ['Modelscore', f"{b['score']}/100"],
        ['Indicatieve jaarwaarde', b['annual_saving']],
        ['Investering rekenbasis', b['investment']],
        ['Ruwe terugverdientijd', b['payback']],
        ['Oordeel', b['advice']],
    ]
    table(c, M, H - 390, W - 2 * M, ['Onderdeel', 'Indicatie'], rows, [.42, .58], 42, 7.5)
    callout(c, M, 55, W - 2 * M, 95, 'Besluitstatus', 'Volgen, nog geen aankoopbesluit. De businesscase wordt opnieuw beoordeeld met meerdere echte maandupdates en consistente zelfconsumptie-/prijsdata.', 'warn')
    footer(c)


def page12(c, d):
    header(c, 12, '11. Aanbevelingen en actiepunten', d['meta']['status'])
    table(c, M, H - 90, W - 2 * M, ['Moment', 'Actie', 'Waarom'], d['actions']['rows'], [.20, .42, .38], 48, 7.5)
    txt(c, M, H - 385, 'Prioriteiten vóór Crash Recovery', 10, True)
    for i, item in enumerate(d['actions']['priorities']):
        yy = H - 430 - i * 48
        c.setFillColor(NAVY)
        c.circle(M + 12, yy + 3, 10, fill=1, stroke=0)
        txt(c, M + 12, yy, str(i + 1), 7, True, white, 'center')
        txt(c, M + 34, yy, item, 8, True)
    callout(c, M, 45, W - 2 * M, 82, 'Standaard workflow', 'Eerst rapport en workflow groen valideren. Pas daarna een complete Crash Recovery maken, zodat de herstelbasis geen bekende rapportfouten bevat.')
    footer(c)


def page13(c, d):
    header(c, 13, '12. Datakwaliteit en broncontrole', d['meta']['status'])
    wrap(c, 'Bronstatus en controles op deze pagina komen uit de rapportadapter. Er worden geen hardcoded groene vinkjes gebruikt.', M, H - 90, W - 2 * M, 8.3, 11, True)
    table(c, M, H - 140, W - 2 * M, ['Bron', 'Status', 'Gebruik / beperking'], d['quality']['sources'], [.28, .24, .48], 39, 7.2)
    txt(c, M, H - 425, 'Controlepunten', 10, True)
    checks = d['quality']['checks']
    for i, check in enumerate(checks):
        label, status, detail = check
        yy = H - 458 - i * 38
        color = GREEN if status == 'ok' else ORANGE if status in ('aandacht', 'niet gebruikt') else RED
        c.setFillColor(color)
        c.circle(M + 8, yy + 2, 7, fill=1, stroke=0)
        txt(c, M + 8, yy - 1, '✓' if status == 'ok' else '!', 7, True, white, 'center')
        txt(c, M + 24, yy + 3, label, 7.5, True)
        txt(c, M + 190, yy + 3, status, 7, True, color)
        wrap(c, detail, M + 265, yy + 3, W - M - (M + 265), 6.6, 8, False, GRAY, 2)
    callout(c, M, 45, W - 2 * M, 85, 'Status', d['quality']['status'], 'warn' if any(row[1] != 'ok' for row in checks) else 'info')
    footer(c)


def generate(data_path, out_path):
    data = json.loads(Path(data_path).read_text(encoding='utf-8'))
    c = canvas.Canvas(str(out_path), pagesize=A4)
    for fn in (page3, page4, page5, page6, page7, page8, page9, page10, page11, page12, page13):
        fn(c, data)
        c.showPage()
    c.save()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--data', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    generate(args.data, args.output)
