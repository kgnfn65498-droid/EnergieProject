from __future__ import annotations
import argparse, json, math
from pathlib import Path
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.colors import HexColor, white, black
from reportlab.pdfbase.pdfmetrics import stringWidth

W, H = A4
NAVY = HexColor('#08386E')
NAVY2 = HexColor('#0B3F7A')
GREEN = HexColor('#12963B')
ORANGE = HexColor('#F59C1A')
RED = HexColor('#D8524D')
BLUE = HexColor('#2378B9')
TEAL = HexColor('#25A7B8')
LIGHT = HexColor('#F3F7FB')
GRID = HexColor('#D8E2EB')
TEXT = HexColor('#17314D')
MUTED = HexColor('#6A7B8D')


def euro(v):
    if not isinstance(v, (int, float)):
        return "Niet beschikbaar"
    s = f"{abs(v):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
    return ('- ' if v < 0 else '') + '€ ' + s

def tariff(v, unit):
    if not isinstance(v, (int, float)):
        return "Niet beschikbaar"
    return f"€ {v:.3f} {unit}".replace('.', ',')


def txt(c, x, y, s, size=6.2, color=TEXT, font='Helvetica', align='left'):
    c.setFillColor(color); c.setFont(font, size)
    if align == 'center': c.drawCentredString(x, y, str(s))
    elif align == 'right': c.drawRightString(x, y, str(s))
    else: c.drawString(x, y, str(s))


def section(c, x, y, w, title):
    c.setFillColor(NAVY); c.roundRect(x, y-15, w, 15, 4, fill=1, stroke=0)
    txt(c, x+10, y-10.8, title.upper(), 8.2, white, 'Helvetica-Bold')


def panel(c, x, y, w, h, radius=7, fill=white):
    c.setFillColor(fill); c.setStrokeColor(GRID); c.setLineWidth(.7)
    c.roundRect(x, y, w, h, radius, fill=1, stroke=1)


def _draw_icon(c, cx, cy, kind, color, scale=1.0):
    """Draw clean vector icons without relying on emoji/font glyphs."""
    c.saveState()
    c.translate(cx, cy); c.scale(scale, scale); cx=0; cy=0
    c.setStrokeColor(color); c.setFillColor(color); c.setLineWidth(1.25 / max(scale, 0.1))
    if kind == 'lightning':
        path=c.beginPath(); path.moveTo(cx-3,cy+8); path.lineTo(cx+2,cy+8); path.lineTo(cx,cy+2); path.lineTo(cx+5,cy+2); path.lineTo(cx-4,cy-9); path.lineTo(cx-1,cy-2); path.lineTo(cx-5,cy-2); path.close(); c.drawPath(path,fill=1,stroke=0)
    elif kind == 'sun':
        c.circle(cx,cy,5,fill=1,stroke=0)
        for a in range(0,360,45):
            r=math.radians(a); c.line(cx+7*math.cos(r),cy+7*math.sin(r),cx+10*math.cos(r),cy+10*math.sin(r))
    elif kind == 'battery':
        c.rect(cx-8,cy-5,14,10,fill=0,stroke=1); c.rect(cx+6,cy-2,2,4,fill=1,stroke=0); c.rect(cx-4,cy-2,6,4,fill=1,stroke=0)
    elif kind == 'flame':
        path=c.beginPath(); path.moveTo(cx,cy+9); path.curveTo(cx-5,cy+3,cx-6,cy-2,cx-1,cy-7); path.curveTo(cx+5,cy-5,cx+6,cy,cx+2,cy+4); path.curveTo(cx+1,cy+1,cx-2,cy,cx,cy+9); path.close(); c.drawPath(path,fill=1,stroke=0)
    elif kind == 'clock':
        c.circle(cx,cy,7,fill=0,stroke=1); c.line(cx,cy,cx,cy+4); c.line(cx,cy,cx+3,cy+1)
    elif kind == 'thermo':
        c.circle(cx,cy-5,3,fill=0,stroke=1); c.roundRect(cx-1.5,cy-6,3,12,1.5,fill=0,stroke=1); c.line(cx,cy-4,cx,cy+4)
    elif kind == 'bars':
        for i,h in enumerate((4,7,10,13)):
            c.rect(cx-8+i*4,cy-7,2.2,h,fill=1,stroke=0)
        c.line(cx-9,cy-7,cx+8,cy-7); c.line(cx-8,cy+5,cx+7,cy+10)
    else:
        c.circle(cx,cy,3.2,fill=1,stroke=0)
    c.restoreState()


def icon_circle(c, x, y, kind, color, radius=10, scale=1.0, circle=False):
    if circle:
        c.setStrokeColor(GRID); c.setFillColor(white); c.setLineWidth(.7); c.circle(x, y, radius, fill=1, stroke=1)
    _draw_icon(c, x, y, kind, color, scale=scale)


def kpi(c, x, y, w, h, title, value, unit, delta, kind, color, divider=False, gas=False):
    if divider:
        c.setStrokeColor(GRID); c.setLineWidth(.7); c.line(x, y+10, x, y+h-10)
    # The reference uses large free-standing icons rather than small icons inside circles.
    icon_x = x + (18 if not gas else 16)
    icon_y = y + h - 34
    icon_scale = 1.55 if not gas else 1.28
    icon_circle(c, icon_x, icon_y, kind, color, scale=icon_scale, circle=False)
    tx=x+w*.64 if not gas else x+w*.61
    txt(c, tx, y+h-22, title, 5.05 if not gas else 4.55, TEXT, 'Helvetica-Bold', 'center')
    txt(c, tx, y+h-49, value, 12.4 if not gas else 10.5, TEXT, 'Helvetica-Bold', 'center')
    if unit: txt(c, tx + (9 if gas else 0), y+h-58, unit, 4.9, TEXT, 'Helvetica-Bold', 'center')
    txt(c, tx, y+9, f"vs LY  {delta}", 5.6 if not gas else 4.9, GREEN, 'Helvetica-Bold', 'center')

def donut(c, cx, cy, r, pct, col1, col2):
    c.setLineWidth(12)
    c.setStrokeColor(col2); c.arc(cx-r, cy-r, cx+r, cy+r, 0, 360)
    c.setStrokeColor(col1); c.arc(cx-r, cy-r, cx+r, cy+r, 90, -360*pct/100)
    c.setLineWidth(1)


def line_chart(c, x, y, w, h, series, colors, labels=None):
    c.setStrokeColor(GRID); c.setLineWidth(.4)
    for i in range(5):
        yy=y+i*h/4; c.line(x,yy,x+w,yy)
    numeric_vals=[float(v) for vals in series.values() for v in vals if isinstance(v,(int,float))]
    maxv=max(numeric_vals) if numeric_vals else 1
    for (name, vals), col in zip(series.items(), colors):
        c.setStrokeColor(col); c.setLineWidth(1.5)
        pts=[]; prev=None; denom=max(1,len(vals)-1)
        for i,v in enumerate(vals):
            if not isinstance(v, (int, float)):
                prev=None; continue
            point=(x+i*w/denom, y+float(v)/maxv*h)
            if prev is not None: c.line(prev[0],prev[1],point[0],point[1])
            pts.append(point); prev=point
        for px,py in pts: c.setFillColor(col); c.circle(px,py,1.4,fill=1,stroke=0)
    if labels:
        for i,l in enumerate(labels): txt(c,x+i*w/(len(labels)-1),y-9,l,4.3,MUTED,align='center')


def bars(c, x, y, w, h, a, b, labels=None):
    n=len(a); maxv=max(max(abs(v) for v in a+b),1); group=w/n
    zero=y+h*.52
    c.setStrokeColor(GRID); c.setLineWidth(.4)
    for frac,label in [(0.12,'-100'),(.32,'-50'),(.52,'0'),(.72,'50')]:
        yy=y+h*frac; c.line(x,yy,x+w,yy); txt(c,x-4,yy-1,label,3.4,MUTED,align='right')
    for i,(va,vb) in enumerate(zip(a,b)):
        bw=group*.22; xx=x+i*group+group*.18
        for val,col,off in [(va,HexColor('#9BA7B3'),0),(vb,GREEN,bw+2)]:
            hh=abs(val)/maxv*h*.42
            c.setFillColor(col)
            c.rect(xx+off, zero if val>=0 else zero-hh, bw, hh, fill=1, stroke=0)
        if labels: txt(c,x+i*group+group/2,y-8,labels[i],3.5,MUTED,align='center')


def nice_axis_step(max_value):
    """Return a readable y-axis step with about 4-7 labels."""
    if max_value <= 0:
        return 10
    raw=max_value/5.0
    magnitude=10 ** math.floor(math.log10(raw))
    normalized=raw/magnitude
    if normalized <= 1:
        nice=1
    elif normalized <= 2:
        nice=2
    elif normalized <= 2.5:
        nice=2.5
    elif normalized <= 5:
        nice=5
    else:
        nice=10
    return max(1, int(nice*magnitude) if float(nice*magnitude).is_integer() else nice*magnitude)


def small_table(c, x, y, widths, rows, row_h=17, header=True, font_size=5.5):
    total=sum(widths)
    for r,row in enumerate(rows):
        yy=y-r*row_h
        if r==0 and header:
            c.setFillColor(NAVY); c.rect(x,yy-row_h,total,row_h,fill=1,stroke=0); col=white; font='Helvetica-Bold'
        else:
            c.setFillColor(LIGHT if r%2==0 else white); c.rect(x,yy-row_h,total,row_h,fill=1,stroke=0); col=TEXT; font='Helvetica'
        xx=x
        for val,wid in zip(row,widths):
            txt(c,xx+5,yy-row_h+5,str(val),font_size,col,font)
            xx+=wid


def build(data, out):
    c=canvas.Canvas(str(out), pagesize=A4)
    margin=14; gap=7; colw=(W-2*margin-gap)/2

    section(c,margin,H-18,colw,'1. Elektriciteitsanalyse')
    section(c,margin+colw+gap,H-18,colw,'2. Gasanalyse')

    # top KPI panels
    y=H-128; ph=79
    panel(c,margin,y,colw,ph); panel(c,margin+colw+gap,y,colw,ph)
    ew=colw/3
    e=data['electricity']
    kpi(c,margin,y,ew,ph,'Verbruik',f"{e['consumption']}",'kWh',f"{e['consumption_vs_ly']:+.0f}%",'lightning',ORANGE)
    kpi(c,margin+ew,y,ew,ph,'Teruglevering',f"{e['feed_in']}",'kWh',f"{e['feed_in_vs_ly']:+.1f}%",'sun',ORANGE,True)
    kpi(c,margin+2*ew,y,ew,ph,'Netto teruglevering',f"+{e['net_feed_in']}",'kWh',f"{e['net_vs_ly']:+.0f}%",'battery',GREEN,True)
    g=data['gas']; gw=colw/4
    degree_days_available=bool(g.get('degree_days_available'))
    gas_kpis=[
        ('Gasverbruik',f"{g['month']}",'m³',f"{g['month_vs_ly']:+.0f}%",'flame',GREEN),
        ('Gemiddeld per dag',f"{g['per_day']:.2f}" if isinstance(g.get('per_day'),(int,float)) else 'n.b.','m³','-' if not isinstance(g.get('per_day_vs_ly'),(int,float)) else f"{g['per_day_vs_ly']:+.1f}%",'clock',GREEN),
        ('Graaddagen',f"{g['degree_days']:.1f}" if degree_days_available and isinstance(g.get('degree_days'),(int,float)) else 'n.b.','GD' if degree_days_available else 'niet gekoppeld','-' if not isinstance(g.get('degree_days_vs_ly'),(int,float)) else f"{g['degree_days_vs_ly']:+.1f}%",'thermo',ORANGE),
        ('Weerscorrectie',f"{g['per_degree_day']:.2f}" if degree_days_available and isinstance(g.get('per_degree_day'),(int,float)) else 'n.b.','m³/GD' if degree_days_available else 'niet toegepast','model' if degree_days_available else '-','bars',ORANGE),
    ]
    for i,(t,v,u,d,gl,col) in enumerate(gas_kpis):
        kpi(c,margin+colw+gap+i*gw,y,gw,ph,t,str(v).replace('.',','),u,d,gl,col,i>0,gas=True)

    # Contract-year tariff split is intentionally omitted until a validated T1/T2 source is supplied.
    y2=H-236; h2=99
    panel(c,margin,y2,colw,h2)
    txt(c,margin+15,y2+h2-16,'Verdeling normaal/dal',5.8,TEXT,'Helvetica-Bold')
    txt(c,margin+15,y2+h2-35,'Niet weergegeven: de rapportadapter heeft voor deze maand geen bronvaste',4.6,TEXT)
    txt(c,margin+15,y2+h2-47,'T1/T2-contractjaarverdeling. Oude voorbeeldpercentages worden niet gebruikt.',4.6,TEXT)
    c.setStrokeColor(ORANGE); c.setFillColor(HexColor('#FFF8E8')); c.roundRect(margin+15,y2+17,colw-30,25,4,fill=1,stroke=1)
    txt(c,margin+25,y2+32,'Status: bronbeperkt — geen 61/39- of 37/63-fixturewaarden.',4.5,ORANGE,'Helvetica-Bold')

    # gas chart and insights
    gx=margin+colw+gap; chartw=colw*.64
    panel(c,gx,y2,chartw,h2); panel(c,gx+chartw+gap,y2,colw-chartw-gap,h2)
    txt(c,gx+10,y2+h2-14,'Gasverbruik per maand (m³)',5.8,TEXT,'Helvetica-Bold')
    # Legend explicitly placed above the plot, as in the approved reference.
    legend_y=y2+h2-28
    gas_colors=[NAVY,ORANGE,GREEN,BLUE]
    for i,(name,col) in enumerate(zip(g['series'].keys(),gas_colors)):
        lx=gx+12+i*48; c.setFillColor(col); c.rect(lx,legend_y-2,5,5,fill=1,stroke=0); txt(c,lx+8,legend_y-1,name,3.7,TEXT)
    # Gas chart with explicit y-axis labels and unit, matching the reference.
    plot_x, plot_y, plot_w, plot_h = gx+24, y2+20, chartw-36, h2-55
    gas_numeric=[float(v) for vals in g['series'].values() for v in vals if isinstance(v,(int,float))]
    maxv=max(gas_numeric) if gas_numeric else 1
    axis_step=nice_axis_step(maxv)
    axis_max=max(axis_step, math.ceil(maxv/axis_step)*axis_step)
    tick=0
    while tick <= axis_max + 1e-9:
        yy=plot_y+(tick/axis_max)*plot_h
        label=str(int(tick)) if float(tick).is_integer() else str(tick).replace('.',',')
        txt(c,plot_x-6,yy-1,label,3.7,MUTED,align='right')
        tick += axis_step
    txt(c,gx+7,plot_y+plot_h/2,'m³',3.8,MUTED,'Helvetica-Bold',align='center')
    line_chart(c,plot_x,plot_y,plot_w,plot_h,g['series'],gas_colors,['jul','aug','sep','okt','nov','dec','jan','feb','mrt','apr','mei','jun'])
    ix=gx+chartw+gap
    txt(c,ix+10,y2+h2-14,'Inzichten',5.8,TEXT,'Helvetica-Bold')
    insights=[('Gasvergelijking gebruikt dezelfde','kalendermaand vorig jaar.'),('Lopend contractjaar toont alleen','werkelijk beschikbare maanden.'),('Graaddagen/weerscorrectie gebruiken','Eindhoven dagtemperaturen (18 C basis).')]
    for i,(line1,line2) in enumerate(insights):
        yy=y2+h2-31-i*25
        c.setFillColor(GREEN if i<2 else ORANGE); c.circle(ix+17,yy,4,fill=1,stroke=0)
        txt(c,ix+26,yy+1,line1,3.9,TEXT); txt(c,ix+26,yy-5,line2,3.9,TEXT)

    # contract table + gas explanation
    y3=H-302; th=60
    panel(c,margin,y3,colw,th); panel(c,gx,y3,colw,th,fill=HexColor('#EEF5FC'))
    rows=[['Contractjaarhistorie','Verbruik','Teruglevering','Netto']]+[[r[0],f"{r[1]:,}".replace(',','.'),f"{r[2]:,}".replace(',','.'),f"{r[3]:,}".replace(',','.')] for r in e['contract_years']]
    small_table(c,margin+5,y3+th-4,[137,43,50,43],rows,row_h=10.5,font_size=4.4)
    txt(c,gx+10,y3+th-14,'Toelichting',5.8,TEXT,'Helvetica-Bold')
    txt(c,gx+10,y3+th-29,g.get('coverage_note','Geen weersverklaring zonder gevalideerde graaddagenbron.'),4.3,TEXT)

    section(c,margin,H-318,colw,'3. Kostenanalyse')
    section(c,gx,H-318,colw,'4. Prognose & trends')

    # cost/prognosis cards - known offer values are always shown; observed all-in stays explicitly unvalidated.
    y4=H-420; ch=87
    left1=colw*.49
    panel(c,margin,y4,left1,ch); panel(c,margin+left1+gap,y4,colw-left1-gap,ch)
    cc=data['costs']
    txt(c,margin+10,y4+ch-14,f"Financieel overzicht ({data.get('meta',{}).get('month','rapportmaand')})",5.8,TEXT,'Helvetica-Bold')
    finance_items=[
        ('Huidige maandtermijn',cc.get('current_monthly_advance')),
        ('Offerteprognose per maand',cc.get('offer_monthly_projection')),
        ('Verwachte jaarkosten',cc.get('offer_annual_projection')),
        ('Verwachte betalingen per jaar',cc.get('expected_annual_payments')),
        ('Verwacht saldo',cc.get('expected_balance')),
    ]
    for i,(lab,val) in enumerate(finance_items):
        yy=y4+ch-28-i*8.6
        txt(c,margin+10,yy,lab,4.15); txt(c,margin+left1-8,yy,euro(val),4.25,TEXT,'Helvetica-Bold','right')
    c.setFillColor(HexColor('#FFF8E8')); c.roundRect(margin+7,y4+6,left1-14,15,3,fill=1,stroke=0)
    txt(c,margin+10,y4+11,'Werkelijke augustus all-in',4.15,ORANGE,'Helvetica-Bold'); txt(c,margin+left1-8,y4+11,'nog niet gevalideerd',3.7,ORANGE,'Helvetica-Bold','right')

    x2=margin+left1+gap; txt(c,x2+10,y4+ch-14,'Tarieven & aannames',5.8,TEXT,'Helvetica-Bold')
    assumption_rows=[
        ('Rapportmaand-contract',cc.get('report_contract_label','NextEnergy dynamisch')),
        ('Nieuwe offerte start',cc.get('offer_starts','3 september 2026')),
        ('Stroomprijs maand',tariff(cc.get('tariff_t1'),'€/kWh') if isinstance(cc.get('tariff_t1'),(int,float)) else 'niet all-in gekoppeld'),
        ('Gasprijs maand',tariff(cc.get('gas_tariff'),'€/m³') if isinstance(cc.get('gas_tariff'),(int,float)) else 'niet all-in gekoppeld'),
        ('Vaste kosten',cc.get('fixed_costs_note','niet gekoppeld')),
    ]
    for i,(lab,val) in enumerate(assumption_rows):
        yy=y4+ch-29-i*10
        txt(c,x2+10,yy,lab,4.15); txt(c,margin+colw-8,yy,str(val),4.0,TEXT,'Helvetica-Bold','right')

    f=data['forecast']; f1=colw*.49
    panel(c,gx,y4,f1,ch); panel(c,gx+f1+gap,y4,colw-f1-gap,ch)
    txt(c,gx+10,y4+ch-14,'Prognose verbruik & teruglevering',5.8,TEXT,'Helvetica-Bold')
    txt(c,gx+10,y4+ch-23,f.get('source_label','NextEnergy-offerteprofiel'),3.7,MUTED)
    pitems=[('Totaal verbruik',f.get('electricity_total'),'kWh'),('Totaal teruglevering',f.get('feed_in_total'),'kWh'),('Netto levering',f.get('net'),'kWh'),('Verschil vorig contractjaar',f.get('current_year_difference'),'kWh'),('Verschil %',f.get('difference_pct'),'%')]
    for i,(lab,val,unit) in enumerate(pitems):
        yy=y4+ch-34-i*9
        txt(c,gx+10,yy,lab,4.45)
        shown='n.b.' if not isinstance(val,(int,float)) else (f'{val:+.1f} {unit}' if i>=3 else f'{val:.0f} {unit}')
        txt(c,gx+f1-8,yy,shown,4.4,GREEN if i>1 else TEXT,'Helvetica-Bold','right')
    xx=gx+f1+gap; txt(c,xx+10,y4+ch-14,'Prognose gasverbruik',5.8,TEXT,'Helvetica-Bold')
    for i,(lab,val,unit) in enumerate([('Totaal gasverbruik',f.get('gas_total'),'m³'),('Verschil vorig contractjaar',f.get('gas_difference'),'m³'),('Verschil %',f.get('gas_difference_pct'),'%')]):
        yy=y4+ch-31-i*14
        txt(c,xx+10,yy,lab,4.45)
        shown='n.b.' if not isinstance(val,(int,float)) else (f'{val:+.1f} {unit}' if i else f'{val:.0f} {unit}')
        txt(c,gx+colw-8,yy,shown,4.4,GREEN if i else TEXT,'Helvetica-Bold','right')
    txt(c,xx+10,y4+8,f.get('reference_label','Officiële eindafrekening 2025-2026'),3.7,MUTED)

    # No fabricated monthly cost curves: explain the data boundary instead.
    y5=H-520; trh=85
    panel(c,margin,y5,colw,trh); panel(c,gx,y5,colw,trh)
    txt(c,margin+12,y5+trh-16,'Kostenreeks per maand',5.8,TEXT,'Helvetica-Bold')
    txt(c,margin+12,y5+trh-34,'Geen grafiek totdat leverancier-all-in maandkosten bronvast zijn.',4.6,TEXT)
    txt(c,margin+12,y5+trh-49,'Dit voorkomt dat marktprijzen of voorbeeldwaarden als factuurkosten worden gepresenteerd.',4.2,MUTED)
    txt(c,gx+12,y5+trh-16,'Jaarprognosebasis',5.8,TEXT,'Helvetica-Bold')
    txt(c,gx+12,y5+trh-34,'NextEnergy-offerteprofiel versus officiële eindafrekening 2025-2026.',4.6,TEXT)
    txt(c,gx+12,y5+trh-49,'De € 1.836 is een offerteprognose, geen optelsom van € 150-termijnen.',4.2,MUTED)

    section(c,margin,H-535,W-2*margin,'5. Thuisbatterij - scenariovergelijking')
    y6=H-682; bh=132; panel(c,margin,y6,W-2*margin,bh)
    batt=data['battery']
    xA=margin+14; wA=176
    xB=xA+wA+17; wB=214
    xC=xB+wB+17; wC=W-margin-12-xC
    txt(c,xA,y6+bh-18,'Woningprofiel',6.2,TEXT,'Helvetica-Bold')
    prof=batt['profile']
    self_text=f"{prof['self_use_pct']}%" if isinstance(prof.get('self_use_pct'),(int,float)) else 'n.b. - PV bronbeperkt'
    shift_text=f"{prof['estimated_shift']} kWh/mnd" if isinstance(prof.get('estimated_shift'),(int,float)) else 'nog niet berekend'
    profile=[('Teruglevering per jaar',f"{prof['annual_feed_in']:,} kWh".replace(',','.')),('Netto levering',f"{prof['net_import']} kWh"),('Eigen verbruik opwek',self_text),('Geschat verschuifbaar',shift_text)]
    for i,(lab,val) in enumerate(profile):
        yy=y6+bh-34-i*13; txt(c,xA,yy,lab,4.35); txt(c,xA+wA-4,yy,val,4.15,TEXT,'Helvetica-Bold','right')
    c.setStrokeColor(BLUE); c.setFillColor(HexColor('#EDF6FD')); c.roundRect(xA,y6+14,wA-4,38,4,fill=1,stroke=1)
    txt(c,xA+8,y6+40,'Technische conclusie',5.2,TEXT,'Helvetica-Bold'); txt(c,xA+8,y6+28,'Veel jaarlijkse teruglevering; exacte zelfconsumptie',3.9); txt(c,xA+8,y6+20,'blijft bronbeperkt en wordt niet verzonnen.',3.9)

    txt(c,xB,y6+bh-18,"Scenario's",6.2,TEXT,'Helvetica-Bold')
    rows=[['Scenario','Capaciteit','Jaarwaarde','Oordeel']]+batt['scenarios']
    small_table(c,xB,y6+bh-26,[72,47,53,37],rows,row_h=18,font_size=3.45)
    txt(c,xB,y6+25,'Één modelbasis in het hele rapport:',4.1,TEXT,'Helvetica-Bold')
    txt(c,xB,y6+15,'Marstek-modelwaarden zijn indicatief en geen gemeten besparing.',3.6,MUTED)

    txt(c,xC,y6+bh-18,'Beslismatrix',6.2,TEXT,'Helvetica-Bold')
    dec=batt['decision']; decisions=[('Technisch passend',dec['technical']),('Financieel overtuigend',dec['financial']),('Beste kandidaat',dec['best']),('Ruwe terugverdientijd',dec['payback']),('Koopadvies',dec['advice'])]
    for i,(lab,val) in enumerate(decisions):
        yy=y6+bh-31-i*11.5; txt(c,xC,yy,lab,4.05); txt(c,xC+wC,yy,str(val),3.85,GREEN if i in (0,2) else ORANGE,'Helvetica-Bold','right')
    c.setStrokeColor(ORANGE); c.setFillColor(HexColor('#FFF8E8')); c.roundRect(xC,y6+12,wC,31,4,fill=1,stroke=1)
    txt(c,xC+8,y6+32,'Actie: volgen, nog geen aankoopbesluit.',4.7,ORANGE,'Helvetica-Bold'); txt(c,xC+8,y6+21,'Herijken met meerdere echte maandupdates.',3.75,TEXT)

    section(c,margin,H-699,W-2*margin,'6. Maandtermijn - financieel advies')
    y7=H-795; fh=81; panel(c,margin,y7,W-2*margin,fh)
    term=data['term']; cardgap=6; cardw=(W-2*margin-3*cardgap-10)/4
    vals=[('Huidige maandtermijn',euro(term['current']),'per maand',GREEN),('Advies maandtermijn',euro(term['advice']),'incl. buffer',ORANGE),('Verwachte jaarkosten',euro(term['annual_cost']),'huidige prognose',GREEN),('Verwacht saldo',euro(term['balance']),'nabetaling voorkomen',ORANGE)]
    for i,(lab,val,sub,col) in enumerate(vals):
        xx=margin+5+i*(cardw+cardgap); c.setStrokeColor(GRID); c.setFillColor(white); c.roundRect(xx,y7+35,cardw,39,5,fill=1,stroke=1)
        txt(c,xx+cardw/2,y7+63,lab,4.6,TEXT,'Helvetica-Bold','center'); txt(c,xx+cardw/2,y7+49,val,8.5,col,'Helvetica-Bold','center'); txt(c,xx+cardw/2,y7+40,sub,3.9,MUTED,align='center')
    c.setFillColor(LIGHT); c.roundRect(margin+6,y7+8,245,20,4,fill=1,stroke=0); txt(c,margin+14,y7+21,'Dekking jaarprognose',4.5,TEXT,'Helvetica-Bold'); c.setFillColor(HexColor('#DCE5EC')); c.roundRect(margin+14,y7+10,175,5,2,fill=1,stroke=0); c.setFillColor(ORANGE); c.roundRect(margin+14,y7+10,175*float(term.get('coverage_pct') or 0)/100,5,2,fill=1,stroke=0); txt(c,margin+239,y7+10,f"{float(term.get('coverage_pct') or 0):.1f}% gedekt".replace('.',','),4.4,ORANGE,'Helvetica-Bold','right')
    c.setStrokeColor(ORANGE); c.setFillColor(HexColor('#FFF8E8')); c.roundRect(margin+258,y7+8,W-margin-(margin+258),20,4,fill=1,stroke=1); txt(c,margin+266,y7+21,'Advies',4.5,ORANGE,'Helvetica-Bold'); txt(c,margin+266,y7+12,f"NextEnergy-offerteprognose: {euro(term['advice'])} per maand.",4.3,TEXT)

    txt(c,W-margin,8,'Energierapport - Pagina 2 | generator v6.0',4.2,MUTED,align='right')
    c.save()


def main():
    p=argparse.ArgumentParser(); p.add_argument('--data',required=True); p.add_argument('--output',required=True); a=p.parse_args()
    with open(a.data,encoding='utf-8') as f: data=json.load(f)
    Path(a.output).parent.mkdir(parents=True,exist_ok=True); build(data,Path(a.output))

if __name__=='__main__': main()
