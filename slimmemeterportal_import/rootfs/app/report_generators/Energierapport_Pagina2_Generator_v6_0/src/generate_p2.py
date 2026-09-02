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
    for i,(t,v,u,d,gl,col) in enumerate([
        ('Gasverbruik',g['month'],'m³',f"{g['month_vs_ly']:+.0f}%",'flame',GREEN),
        ('Gemiddeld per dag',g['per_day'],'m³',f"{g['per_day_vs_ly']:+.1f}%",'clock',GREEN),
        ('Warmtegraaddagen',f"{g['degree_days']:,}".replace(',','.'),'',f"{g['degree_days_vs_ly']:+.1f}%",'thermo',GREEN),
        ('Verbruik / graaddag',g['per_degree_day'],'m³',f"{g['per_degree_day_vs_ly']:+.1f}%",'bars',GREEN)]):
        kpi(c,margin+colw+gap+i*gw,y,gw,ph,t,str(v).replace('.',','),u,d,gl,col,i>0,gas=True)

    # middle left electricity split + table
    y2=H-236; h2=99
    panel(c,margin,y2,colw,h2)
    txt(c,margin+15,y2+h2-14,'Verdeling verbruik huidig contractjaar',5.4,TEXT,'Helvetica-Bold')
    txt(c,margin+colw/2+8,y2+h2-14,'Verdeling teruglevering huidig contractjaar',5.4,TEXT,'Helvetica-Bold')
    cs=e['consumption_split']; fs=e['feedin_split']
    donut(c,margin+72,y2+49,22,cs['t1_pct'],ORANGE,BLUE)
    txt(c,margin+31,y2+53,f"{cs['t1_pct']}%",8,ORANGE,'Helvetica-Bold','center'); txt(c,margin+31,y2+42,f"{cs['t1_kwh']:,} kWh".replace(',','.'),4.5,ORANGE,align='center'); txt(c,margin+113,y2+53,f"{cs['t2_pct']}%",8,BLUE,'Helvetica-Bold','center'); txt(c,margin+113,y2+42,f"{cs['t2_kwh']:,} kWh".replace(',','.'),4.5,BLUE,align='center')
    donut(c,margin+colw/2+72,y2+49,22,fs['t1_pct'],ORANGE,BLUE)
    txt(c,margin+colw/2+31,y2+53,f"{fs['t1_pct']}%",8,ORANGE,'Helvetica-Bold','center'); txt(c,margin+colw/2+31,y2+42,f"{fs['t1_kwh']:,} kWh".replace(',','.'),4.5,ORANGE,align='center'); txt(c,margin+colw/2+113,y2+53,f"{fs['t2_pct']}%",8,BLUE,'Helvetica-Bold','center'); txt(c,margin+colw/2+113,y2+42,f"{fs['t2_kwh']:,} kWh".replace(',','.'),4.5,BLUE,align='center')
    c.setFillColor(ORANGE); c.rect(margin+33,y2+12,5,5,fill=1,stroke=0); txt(c,margin+44,y2+13,'T1 Normaal (dag)',4.1,MUTED); c.setFillColor(BLUE); c.rect(margin+126,y2+12,5,5,fill=1,stroke=0); txt(c,margin+137,y2+13,'T2 Dal (nacht)',4.1,MUTED)
    c.setFillColor(ORANGE); c.rect(margin+colw/2+33,y2+12,5,5,fill=1,stroke=0); txt(c,margin+colw/2+44,y2+13,'T1 Normaal (dag)',4.1,MUTED); c.setFillColor(BLUE); c.rect(margin+colw/2+126,y2+12,5,5,fill=1,stroke=0); txt(c,margin+colw/2+137,y2+13,'T2 Dal (nacht)',4.1,MUTED)

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
    axis_max=max(10,math.ceil(maxv/10)*10)
    for tick in range(0, axis_max+1, 10):
        yy=plot_y+(tick/axis_max)*plot_h
        txt(c,plot_x-6,yy-1,str(tick),3.7,MUTED,align='right')
    txt(c,gx+7,plot_y+plot_h/2,'m³',3.8,MUTED,'Helvetica-Bold',align='center')
    line_chart(c,plot_x,plot_y,plot_w,plot_h,g['series'],gas_colors,['jul','aug','sep','okt','nov','dec','jan','feb','mrt','apr','mei','jun'])
    ix=gx+chartw+gap
    txt(c,ix+10,y2+h2-14,'Inzichten',5.8,TEXT,'Helvetica-Bold')
    insights=[('Gasvergelijking gebruikt dezelfde','kalendermaand vorig jaar.'),('Lopend contractjaar toont alleen','werkelijk beschikbare maanden.'),('Geen weersverklaring zonder','gevalideerde graaddagenbron.')]
    for i,(line1,line2) in enumerate(insights):
        yy=y2+h2-31-i*25
        c.setFillColor(GREEN if i<2 else ORANGE); c.circle(ix+17,yy,4,fill=1,stroke=0)
        txt(c,ix+26,yy+1,line1,3.9,TEXT); txt(c,ix+26,yy-5,line2,3.9,TEXT)

    # contract table + gas explanation
    y3=H-302; th=60
    panel(c,margin,y3,colw,th); panel(c,gx,y3,colw,th,fill=HexColor('#EEF5FC'))
    rows=[['Contractjaar (15 jul - 15 jul)','Verbruik','Teruglevering','Netto']]+[[r[0],f"{r[1]:,}".replace(',','.'),f"{r[2]:,}".replace(',','.'),f"{r[3]:,}".replace(',','.')] for r in e['contract_years']]
    small_table(c,margin+5,y3+th-4,[137,43,50,43],rows,row_h=10.5,font_size=4.4)
    txt(c,gx+10,y3+th-14,'Toelichting',5.8,TEXT,'Helvetica-Bold')
    txt(c,gx+10,y3+th-29,'Het gasverbruik is beïnvloed door het weer (minder graaddagen) en efficiënt verwarmen met de airco.',4.8,TEXT)

    section(c,margin,H-318,colw,'3. Kostenanalyse')
    section(c,gx,H-318,colw,'4. Prognose & trends')

    # cost/prognosis cards
    y4=H-420; ch=87
    left1=colw*.49
    panel(c,margin,y4,left1,ch); panel(c,margin+left1+gap,y4,colw-left1-gap,ch)
    txt(c,margin+10,y4+ch-14,f"Kostenoverzicht ({data.get('meta',{}).get('month','rapportmaand')})",5.8,TEXT,'Helvetica-Bold')
    cc=data['costs']; items=[('Stroomkosten',cc['electricity']),('Terugleververgoeding',-cc['feed_in_compensation'] if isinstance(cc.get('feed_in_compensation'), (int,float)) else None),('Netto stroomkosten',(cc['electricity'] + cc['feed_in_compensation']) if isinstance(cc.get('electricity'), (int,float)) and isinstance(cc.get('feed_in_compensation'), (int,float)) else None),('Gaskosten',cc['gas']),('Vaste kosten / netbeheer',cc['grid_costs'])]
    for i,(lab,val) in enumerate(items):
        yy=y4+ch-28-i*8.6
        txt(c,margin+10,yy,lab,4.25); txt(c,margin+left1-8,yy,euro(val) if i<4 else 'apart op nota',4.25,TEXT,'Helvetica-Bold','right')
    c.setFillColor(HexColor('#E8F7EB')); c.roundRect(margin+7,y4+6,left1-14,15,3,fill=1,stroke=0)
    txt(c,margin+10,y4+11,'VARIABELE ENERGIEKOSTEN',4.7,GREEN,'Helvetica-Bold'); txt(c,margin+left1-8,y4+11,euro(cc['variable_total']),7,GREEN,'Helvetica-Bold','right')
    x2=margin+left1+gap; txt(c,x2+10,y4+ch-14,'Tarieven & aannames',5.8,TEXT,'Helvetica-Bold'); txt(c,x2+10,y4+ch-25,'(NextEnergy dynamisch)',4.5,MUTED)
    tariffs=[('Stroomprijs T1 (dag)',cc['tariff_t1'],'€/kWh'),('Stroomprijs T2 (nacht)',cc['tariff_t2'],'€/kWh'),('Terugleververgoeding',cc['feed_in_tariff'],'€/kWh'),('Gasprijs',cc['gas_tariff'],'€/m³')]
    for i,(lab,val,u) in enumerate(tariffs):
        yy=y4+ch-39-i*8.2
        txt(c,x2+10,yy,lab,4.35)
        txt(c,margin+colw-8,yy,tariff(val,u),4.35,TEXT,'Helvetica-Bold','right')
    yy=y4+ch-39-len(tariffs)*8.2
    txt(c,x2+10,yy,'Vaste kosten',4.35)
    txt(c,margin+colw-8,yy,cc.get('fixed_costs_note','volgens nota'),4.35,TEXT,'Helvetica-Bold','right')

    f=data['forecast']; f1=colw*.49
    panel(c,gx,y4,f1,ch); panel(c,gx+f1+gap,y4,colw-f1-gap,ch)
    txt(c,gx+10,y4+ch-14,'Prognose verbruik & teruglevering',5.8,TEXT,'Helvetica-Bold')
    pitems=[('Totaal verbruik',f.get('electricity_total')),('Totaal teruglevering',f.get('feed_in_total')),('Netto levering',f.get('net')),('Verschil vorig contractjaar',f.get('current_year_difference')),('Verschil %',f.get('difference_pct'))]
    for i,(lab,val) in enumerate(pitems): txt(c,gx+10,y4+ch-29-i*9,lab,4.6); txt(c,gx+f1-8,y4+ch-29-i*9,'Niet beschikbaar' if not isinstance(val,(int,float)) else (f'{val:+.1f}%' if i==4 else f'{val:+.1f}' if i==3 else f'{val:.1f}'),4.6,GREEN if i>1 else TEXT,'Helvetica-Bold','right')
    xx=gx+f1+gap; txt(c,xx+10,y4+ch-14,'Prognose gasverbruik',5.8,TEXT,'Helvetica-Bold')
    for i,(lab,val) in enumerate([('Totaal gasverbruik',f.get('gas_total')),('Verschil vorig contractjaar',f.get('gas_difference')),('Verschil %',f.get('gas_difference_pct'))]): txt(c,xx+10,y4+ch-30-i*13,lab,4.6); txt(c,gx+colw-8,y4+ch-30-i*13,'Niet beschikbaar' if not isinstance(val,(int,float)) else (f'{val:+.1f}%' if i==2 else f'{val:+.1f}' if i==1 else f'{val:.1f}'),4.6,GREEN if i else TEXT,'Helvetica-Bold','right')

    # two trend panels
    y5=H-520; trh=85
    panel(c,margin,y5,colw,trh); panel(c,gx,y5,colw,trh)
    txt(c,margin+colw/2,y5+trh-14,'Kostentrend per maand (netto, €)',5.8,TEXT,'Helvetica-Bold','center'); c.setFillColor(HexColor('#9BA7B3')); c.rect(margin+18,y5+trh-29,5,5,fill=1,stroke=0); txt(c,margin+27,y5+trh-27,'Vorig jaar',4.5,MUTED,'Helvetica-Bold'); c.setFillColor(GREEN); c.rect(margin+72,y5+trh-29,5,5,fill=1,stroke=0); txt(c,margin+81,y5+trh-27,'Huidig jaar',4.5,MUTED,'Helvetica-Bold')
    # Extra ruimte onder de grafiek voor een blijvend zichtbare x-as met maandlabels.
    bars(c,margin+22,y5+30,colw-40,trh-56,cc['trend_previous'],cc['trend_current'],['jul','aug','sep','okt','nov','dec','jan','feb','mrt','apr','mei','jun'])
    c.setFillColor(HexColor('#EEF5FC')); c.roundRect(margin+8,y5+5,colw-16,12,2,fill=1,stroke=0); txt(c,margin+12,y5+9,'Negatieve waarde = voordeel door teruglevering hoger dan kosten.',3.4,MUTED); txt(c,gx+colw/2,y5+trh-14,'Maandprognose netto kosten (€/maand)',5.8,TEXT,'Helvetica-Bold','center'); txt(c,gx+18,y5+trh-27,'■ Werkelijk       ■ Prognose',3.8,MUTED)
    line_chart(c,gx+20,y5+18,colw-35,trh-42,{'Werkelijk':f['monthly_actual'],'Prognose':f['monthly_forecast']},[HexColor('#8C969F'),GREEN],['jul','aug','sep','okt','nov','dec','jan','feb','mrt','apr','mei','jun'])

    section(c,margin,H-535,W-2*margin,'5. Thuisbatterij - scenariovergelijking')
    y6=H-682; bh=132; panel(c,margin,y6,W-2*margin,bh)
    batt=data['battery']
    # Three independently bounded columns, matching the reference proportions.
    xA=margin+14; wA=176
    xB=xA+wA+17; wB=214
    xC=xB+wB+17; wC=W-margin-12-xC
    txt(c,xA,y6+bh-18,'Woningprofiel',6.2,TEXT,'Helvetica-Bold')
    profile=[('Teruglevering per jaar',f"{batt['profile']['annual_feed_in']:,} kWh".replace(',','.')),('Netto levering',f"{batt['profile']['net_import']} kWh"),('Eigen verbruik opwek',f"{batt['profile']['self_use_pct']}%"),('Geschat verschuifbaar',f"{batt['profile']['estimated_shift']} kWh/mnd")]
    for i,(lab,val) in enumerate(profile):
        yy=y6+bh-34-i*13; txt(c,xA,yy,lab,4.5); txt(c,xA+wA-4,yy,val,4.5,TEXT,'Helvetica-Bold','right')
    c.setStrokeColor(BLUE); c.setFillColor(HexColor('#EDF6FD')); c.roundRect(xA,y6+14,wA-4,38,4,fill=1,stroke=1)
    txt(c,xA+8,y6+40,'Technische conclusie',5.2,TEXT,'Helvetica-Bold'); txt(c,xA+8,y6+28,'Veel teruglevering overdag en gelijktijdige',4.0); txt(c,xA+8,y6+20,'netafname op andere momenten.',4.0)

    txt(c,xB,y6+bh-18,"Scenario's",6.2,TEXT,'Helvetica-Bold')
    rows=[['Scenario','Capaciteit','Jaarwaarde','Oordeel']]+batt['scenarios']
    small_table(c,xB,y6+bh-26,[58,48,56,47],rows,row_h=15,font_size=3.55)
    txt(c,xB,y6+20,'Relatieve jaarwaarde',4.2,TEXT,'Helvetica-Bold')
    for i,(lab,pct,colr) in enumerate([('Geen',0,HexColor('#9BA7B3')),('2,7',.42,BLUE),('5,1',.72,GREEN),('Vast',.62,ORANGE)]):
        xx=xB+63+i*38
        c.setFillColor(HexColor('#DCE6EE')); c.roundRect(xx,y6+15,25,6,3,fill=1,stroke=0)
        if pct > 0:
            c.setFillColor(colr); c.roundRect(xx,y6+15,25*pct,6,min(3,25*pct/2),fill=1,stroke=0)
        txt(c,xx+12.5,y6+7,lab,3.3,MUTED,align='center')

    txt(c,xC,y6+bh-18,'Beslismatrix',6.2,TEXT,'Helvetica-Bold')
    dec=batt['decision']; decisions=[('Technisch passend',dec['technical']),('Financieel overtuigend',dec['financial']),('Beste kandidaat',dec['best']),('Ruwe terugverdientijd',dec['payback']),('Koopadvies',dec['advice'])]
    for i,(lab,val) in enumerate(decisions):
        yy=y6+bh-31-i*11.5; txt(c,xC,yy,lab,4.15); txt(c,xC+wC,yy,val,4.25,GREEN if i in (0,2) else ORANGE,'Helvetica-Bold','right')
    c.setStrokeColor(ORANGE); c.setFillColor(HexColor('#FFF8E8')); c.roundRect(xC,y6+12,wC,31,4,fill=1,stroke=1)
    txt(c,xC+8,y6+32,'Actie: nog geen aankoopbesluit.',4.9,ORANGE,'Helvetica-Bold'); txt(c,xC+8,y6+21,'Opnieuw beoordelen na meerdere echte maandupdates.',3.75,TEXT)

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
