#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, math
from pathlib import Path
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.colors import HexColor, white
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.lib.utils import ImageReader
from validate_maanddata import load_and_validate

W,H=A4
SX=W/1985.0; SY=H/2807.0
C={"rood":HexColor('#F2484B'),"groen":HexColor('#099A3F'),"oranje":HexColor('#FF8A00'),"blauw":HexColor('#1676D2'),"paars":HexColor('#7A35A5'),"turkoois":HexColor('#22A6A6'),"navy":HexColor('#0B3269'),"blue":HexColor('#1676D2'),"green":HexColor('#099A3F'),"red":HexColor('#F2484B'),"orange":HexColor('#FF8A00'),"purple":HexColor('#7A35A5'),"teal":HexColor('#22A6A6'),"ink":HexColor('#0B2B57'),"muted":HexColor('#63758F'),"line":HexColor('#C8D5E4'),"pale":HexColor('#EEF5FB'),"lightgreen":HexColor('#EAF7ED')}

def X(px): return px*SX
def Y(py): return H-py*SY

def rr(c,x,y,w,h,r=18,fill=white,stroke=None,lw=2):
    c.setLineWidth(lw*SX); c.setStrokeColor(stroke or C['line']); c.setFillColor(fill)
    c.roundRect(X(x),Y(y+h),X(w),h*SY,r*SX,fill=1,stroke=1)

def txt(c,s,x,y,size=24,bold=False,color='ink',align='left'):
    font='Helvetica-Bold' if bold else 'Helvetica'; c.setFont(font,size*SX); c.setFillColor(C.get(color,color if hasattr(color,'red') else C['ink']))
    xx=X(x)
    if align=='center': xx-=stringWidth(str(s),font,size*SX)/2
    elif align=='right': xx-=stringWidth(str(s),font,size*SX)
    c.drawString(xx,Y(y),str(s))

def wrap(c,s,x,y,w,size=20,leading=25,bold=False,color='ink',max_lines=6):
    words=s.split(); lines=[]; cur=''; font='Helvetica-Bold' if bold else 'Helvetica'; fs=size*SX
    for word in words:
        cand=(cur+' '+word).strip()
        if stringWidth(cand,font,fs)<=X(w): cur=cand
        else:
            if cur: lines.append(cur)
            cur=word
    if cur: lines.append(cur)
    lines=lines[:max_lines]
    for i,line in enumerate(lines): txt(c,line,x,y+i*leading,size,bold,color)
    return len(lines)

def section(c,n,title,y,x=27,w=1931):
    c.setFillColor(C['navy']); c.roundRect(X(x),Y(y+52),X(w),52*SY,10*SX,fill=1,stroke=0)
    txt(c,f'{n}  {title}',x+28,y+37,27,True,white)

def icon(c,kind,cx,cy,color):
    col=C[color]
    c.setStrokeColor(col); c.setFillColor(white); c.setLineWidth(4*SX)
    c.roundRect(X(cx-31),Y(cy+31),X(62),62*SY,14*SX,fill=1,stroke=1)
    c.setStrokeColor(col); c.setFillColor(col); c.setLineWidth(4*SX)
    px=X(cx); py=Y(cy)
    if kind=='euro':
        txt(c,'€',cx,cy+10,30,True,col,'center')
    elif kind=='huis':
        p=c.beginPath(); p.moveTo(X(cx-18),Y(cy)); p.lineTo(X(cx),Y(cy-18)); p.lineTo(X(cx+18),Y(cy)); p.lineTo(X(cx+14),Y(cy+18)); p.lineTo(X(cx-14),Y(cy+18)); p.close(); c.drawPath(p,fill=0,stroke=1)
    elif kind=='vlam':
        p=c.beginPath(); p.moveTo(px,Y(cy+18)); p.curveTo(X(cx-17),Y(cy+7),X(cx-8),Y(cy-13),px,Y(cy-18)); p.curveTo(X(cx+14),Y(cy-8),X(cx+10),Y(cy+7),px,Y(cy+18)); c.drawPath(p,fill=1,stroke=0)
    elif kind=='zon':
        c.circle(px,py,10*SX,fill=0,stroke=1)
        for a in range(0,360,45):
            c.line(px+math.cos(math.radians(a))*15*SX,py+math.sin(math.radians(a))*15*SX,px+math.cos(math.radians(a))*22*SX,py+math.sin(math.radians(a))*22*SX)
    elif kind=='bliksem':
        p=c.beginPath(); p.moveTo(X(cx+6),Y(cy-20)); p.lineTo(X(cx-8),Y(cy)); p.lineTo(X(cx+2),Y(cy)); p.lineTo(X(cx-5),Y(cy+20)); p.lineTo(X(cx+12),Y(cy-3)); p.lineTo(X(cx+2),Y(cy-3)); p.close(); c.drawPath(p,fill=1,stroke=0)
    elif kind=='balans':
        c.line(X(cx-16),Y(cy-7),X(cx+16),Y(cy-7)); c.line(X(cx-16),Y(cy+7),X(cx+16),Y(cy+7))
        c.line(X(cx-16),Y(cy-7),X(cx-8),Y(cy-15)); c.line(X(cx-16),Y(cy-7),X(cx-8),Y(cy+1))
        c.line(X(cx+16),Y(cy+7),X(cx+8),Y(cy-1)); c.line(X(cx+16),Y(cy+7),X(cx+8),Y(cy+15))
    elif kind=='meter':
        c.arc(X(cx-18),Y(cy+18),X(cx+18),Y(cy-18),0,180)
        c.line(px,py,X(cx+11),Y(cy-9)); c.circle(px,py,2*SX,fill=1,stroke=0)
    elif kind=='kaart':
        c.roundRect(X(cx-14),Y(cy+10),X(28),20*SY,4*SX,fill=0,stroke=1); c.line(X(cx-10),Y(cy+2),X(cx+10),Y(cy+2))
    elif kind=='grafiek':
        c.line(X(cx-15),Y(cy+14),X(cx-15),Y(cy-14)); c.line(X(cx-15),Y(cy+14),X(cx+15),Y(cy+14))
        p=c.beginPath(); p.moveTo(X(cx-10),Y(cy+8)); p.lineTo(X(cx-3),Y(cy+1)); p.lineTo(X(cx+3),Y(cy+6)); p.lineTo(X(cx+12),Y(cy-7)); c.drawPath(p,fill=0,stroke=1)
    elif kind=='plusminus':
        c.line(X(cx-14),py,X(cx-2),py); c.line(X(cx-8),Y(cy-6),X(cx-8),Y(cy+6)); c.line(X(cx+3),py,X(cx+15),py)
    elif kind=='doel':
        c.circle(px,py,14*SX,fill=0,stroke=1); c.circle(px,py,7*SX,fill=0,stroke=1); c.circle(px,py,2*SX,fill=1,stroke=0)
    elif kind=='verschil':
        c.line(X(cx-10),Y(cy-14),X(cx-10),Y(cy+14)); c.line(X(cx+10),Y(cy-14),X(cx+10),Y(cy+14))
        c.line(X(cx-16),Y(cy-8),X(cx-10),Y(cy-14)); c.line(X(cx-4),Y(cy-8),X(cx-10),Y(cy-14))
        c.line(X(cx+4),Y(cy+8),X(cx+10),Y(cy+14)); c.line(X(cx+16),Y(cy+8),X(cx+10),Y(cy+14))
    else:
        c.circle(px,py,7*SX,fill=1,stroke=0)

def header(c,d,assets):
    c.setFillColor(C['navy']); c.rect(X(27),Y(420),X(1931),420*SY,fill=1,stroke=0)
    txt(c,'ENERGIERAPPORT',74,97,73,True,white)
    txt(c,f"Managementoverzicht - Pagina 1 van {d['rapport']['paginas']}",74,161,26,True,white)
    txt(c,'Periode:',74,250,21,True,white); txt(c,d['rapport']['periode'],74,284,25,False,white)
    txt(c,'Rapportdatum:',74,354,21,True,white); txt(c,d['rapport']['rapportdatum'],74,388,25,False,white)
    img=ImageReader(str(assets/'woning.png')); c.drawImage(img,X(792),Y(410),X(350),382*SY,mask='auto',preserveAspectRatio=True,anchor='c')
    txt(c,'NEXT',1480,95,62,True,white); txt(c,'ENERGY',1668,95,62,True,C['green']); txt(c,'ENERGY FOR HAPPINESS',1480,135,23,False,HexColor('#AFC2DD'))
    c.setFillColor(white); c.rect(X(1482),Y(236),X(20),20*SY,fill=1,stroke=0); txt(c,'Contract start',1544,230,19,True,white); txt(c,d['contract']['start'],1544,264,20,False,white)
    c.rect(X(1482),Y(356),X(20),20*SY,fill=1,stroke=0); txt(c,'Contract',1544,350,19,True,white); txt(c,d['contract']['type'],1544,384,20,False,white)

def draw_kpis(c,d):
    x0=619; topy=510; gap=12; w=181; h=270
    for i,k in enumerate(d['kpi_boven']):
        x=x0+i*(w+gap); rr(c,x,topy,w,h,24)
        icon(c,k['icoon'],x+w/2,topy+48,k['kleur'])
        txt(c,k['titel'],x+w/2,topy+122,16,True,'ink','center')
        txt(c,k['waarde'],x+w/2,topy+178,35,True,'ink','center')
        txt(c,k['eenheid'],x+w/2,topy+210,17,True,'ink','center')
        txt(c,k['delta'],x+w/2,topy+238,17,True,k['kleur'],'center')
        txt(c,d['rapport'].get('comparison_label','VS. VORIG JAAR'),x+w/2,topy+263,13,True,'muted','center')
    w2=214; y2=804; h2=260
    icon_kinds=['euro','kaart','grafiek','plusminus','doel','verschil']
    for i,k in enumerate(d['kpi_onder']):
        x=x0+i*(w2+11); rr(c,x,y2,w2,h2,22)
        icon(c,icon_kinds[i],x+w2/2,y2+46,k['kleur'])
        txt(c,k['titel'],x+w2/2,y2+126,15,True,'ink','center')
        txt(c,k['waarde'],x+w2/2,y2+188,31,True,'ink','center')
        txt(c,k['sub'],x+w2/2,y2+226,17,True,k['kleur'],'center')

SUMMARY_COLOR_ORDER = {'groen': 0, 'oranje': 1, 'rood': 2}

def sorted_summary_items(items):
    """Sorteer stabiel op statuskleur: groen, oranje, rood.

    De oorspronkelijke volgorde binnen dezelfde kleur blijft behouden.
    """
    return sorted(items, key=lambda item: SUMMARY_COLOR_ORDER[item['kleur']])

def draw_summary(c,d):
    rr(c,27,510,572,554,24)
    yy=566
    for item in sorted_summary_items(d['samenvatting']):
        col={'groen':'green','oranje':'orange','rood':'red'}[item['kleur']]
        c.setFillColor(C[col]); c.circle(X(64),Y(yy),10*SX,fill=1,stroke=0)
        n=wrap(c,item['tekst'],96,yy+5,455,18,23,True,'ink',3); yy += max(58,n*23+18)

def draw_month(c,d):
    rr(c,27,1140,1931,464,24)
    labels=[('Elektriciteitsverbruik','bliksem','red',d['maand']['verbruik']),('Teruglevering','zon','green',d['maand']['teruglevering']),('Gasverbruik','vlam','blue',d['maand']['gas'])]
    for r,(lab,ic,col,val) in enumerate(labels):
        y=1168+r*145; rr(c,50,y,935,126,18)
        icon(c,ic,106,y+62,col)
        txt(c,lab,156,y+38,18,True)
        txt(c,f"{val['waarde']:.1f}".replace('.',',')+' '+('m³' if lab=='Gasverbruik' else 'kWh'),156,y+82,30,True)
        txt(c,f"({val['delta']:+.1f})".replace('.',','),350,y+82,18,True,'green' if val['delta']>0 and lab=='Teruglevering' else 'red')
        report_year=int(str(d['rapport'].get('maand','')).split()[-1]) if str(d['rapport'].get('maand','')).split()[-1].isdigit() else 2026; years=[str(report_year-3),str(report_year-2),str(report_year-1),str(report_year)]; numeric_years=[v for v in val['jaren'] if isinstance(v,(int,float))]; mx=max(numeric_years) if numeric_years else 1
        chart_x=485; chart_w=395
        for j,v in enumerate(val['jaren']):
            yy=y+22+j*24
            txt(c,years[j],chart_x-18,yy+10,11,False,'muted','right')
            if not isinstance(v,(int,float)):
                txt(c,'-',chart_x+10,yy+11,11,False,'muted')
                continue
            bw=chart_w*(v/mx) if mx else 0
            fill=HexColor('#F3B9BC') if col=='red' else HexColor('#BDE6CD') if col=='green' else HexColor('#B9D3EB')
            if j==3: fill=C[col]
            c.setFillColor(fill); c.roundRect(X(chart_x),Y(yy+18),X(bw),14*SY,5*SX,fill=1,stroke=0)
            txt(c,str(v).replace('.',','),chart_x+bw+10,yy+11,11,False,'muted')
        txt(c,d['rapport'].get('comparison_label','VS. VORIG JAAR'),156,y+111,12,True,'muted')
    rr(c,1015,1168,918,412,20)
    txt(c,'NETTO ELEKTRICITEITSBALANS PER MAAND (kWh)',1474,1212,24,True,'ink','center')
    top=1264; bottom=1532; vals=d['maand']['netto_maanden']; months=['jul','aug','sep','okt','nov','dec','jan','feb','mrt','apr','mei','jun']
    numeric_vals=[float(v) for v in vals if isinstance(v,(int,float))]
    cumulative_points=[0.0]
    cumulative=0.0
    for v in vals:
        if isinstance(v,(int,float)):
            cumulative += float(v)
            cumulative_points.append(cumulative)
    extent=max([abs(v) for v in cumulative_points] + [abs(v) for v in numeric_vals] + [1.0])
    scale=(bottom-top-24)/extent
    def cy(value): return top + abs(float(value))*scale
    c.setStrokeColor(C['line']); c.line(X(1090),Y(top),X(1900),Y(top)); c.line(X(1090),Y(bottom),X(1900),Y(bottom))
    txt(c,'0',1100,top+3,11,False,'muted','right')
    cumulative=0.0
    for i,v in enumerate(vals):
        x=1130+i*63
        if not isinstance(v,(int,float)):
            txt(c,'-',x+15,top+18,10,True,'muted','center'); txt(c,months[i],x+15,1554,11,False,'muted','center'); continue
        start=cumulative; cumulative += float(v)
        y1=cy(start); y2=cy(cumulative); bar_top=min(y1,y2); bar_h=max(2.0,abs(y2-y1))
        c.setFillColor(C['green'] if v<=0 else C['red']); c.rect(X(x),Y(bar_top+bar_h),X(30),bar_h*SY,fill=1,stroke=0)
        if i < len(vals)-1:
            c.setStrokeColor(C['line']); c.line(X(x+30),Y(y2),X(x+63),Y(y2))
        label=f"{float(v):+.1f}".replace('.',',').replace('+','')
        txt(c,label,x+15,max(top+18,bar_top-7),10,True,'green' if v<=0 else 'red','center'); txt(c,months[i],x+15,1554,11,False,'muted','center')
    total=cumulative; total_h=max(2.0,abs(cy(total)-cy(0.0)))
    c.setFillColor(C['navy']); c.rect(X(1860),Y(top+total_h),X(30),total_h*SY,fill=1,stroke=0)
    txt(c,f"{total:.1f}".replace('.',','),1875,top+total_h-7,11,True,white,'center')
    txt(c,'Totaal',1875,1572,11,False,'muted','center')

def gauge(c,cx,cy,r,score,color='green',segments=False):
    c.setLineWidth(28*SX)
    c.setStrokeColor(HexColor('#D9DEE5'))
    c.arc(X(cx-r),Y(cy+r),X(cx+r),Y(cy-r),0,180)
    if segments:
        # Five equal score bands on one exact horizontal semicircle.
        # Draw from the left baseline to the right baseline, like the approved reference.
        bands=[(144,36,'red'),(108,36,'orange'),(72,36,'orange'),(36,36,'green'),(0,36,'green')]
        for start,extent,col in bands:
            c.setStrokeColor(C[col])
            c.arc(X(cx-r),Y(cy+r),X(cx+r),Y(cy-r),start,extent)
        # Clean and emphasize the common horizontal baseline endpoints.
        c.setLineWidth(2*SX)
        c.setStrokeColor(C['line'])
        c.line(X(cx-r),Y(cy),X(cx+r),Y(cy))
    else:
        # Fill from the left side toward the right; leave the final remainder gray.
        extent=180*score/100.0
        c.setStrokeColor(C[color]); c.arc(X(cx-r),Y(cy+r),X(cx+r),Y(cy-r),180-extent,extent)

def draw_score_eff(c,d):
    rr(c,27,1690,953,486,24); rr(c,1005,1690,953,486,24)
    score_available=bool(d.get('score',{}).get('score_beschikbaar',True))
    score=float(d.get('score',{}).get('totaal') or 0)
    gauge(c,255,1848,105,score,'red',segments=True)
    if score_available:
        c.setStrokeColor(C['ink']); c.setLineWidth(7*SX); c.line(X(255),Y(1848),X(205),Y(1829))
        txt(c,int(score) if score.is_integer() else score,255,1908,50,True,'ink','center'); txt(c,'/100',255,1950,16,True,'ink','center')
        txt(c,'VOORLOPIGE ENERGIESCORE',255,2012,16,True,'orange','center')
    else:
        txt(c,'N/B',255,1918,44,True,'muted','center')
        txt(c,'ENERGIESCORE NOG NIET BEREKENBAAR',255,2012,14,True,'orange','center')
    names=d.get('score',{}).get('onderdelen') or []
    cols=['orange','orange','green','green','green']
    for i,(name,val) in enumerate(names[:5]):
        y=1768+i*49; col=cols[i]
        c.setFillColor(C[col] if score_available else C['line']); c.circle(X(432),Y(y-4),8*SX,fill=1,stroke=0)
        txt(c,name,465,y,17,True)
        shown=f'{val} / 100' if score_available and isinstance(val,(int,float)) else 'n.b.'
        txt(c,shown,880,y,15,True,'ink','right')
        c.setFillColor(C['line']); c.roundRect(X(465),Y(y+18),X(420),12*SY,6*SX,fill=1,stroke=0)
        if score_available and isinstance(val,(int,float)):
            c.setFillColor(C[col]); c.roundRect(X(465),Y(y+18),X(420*val/100),12*SY,6*SX,fill=1,stroke=0)
    rr(c,58,2025,860,112,16,fill=C['pale'],stroke=C['blue'])
    txt(c,'Toelichting energiescore',82,2060,18,True)
    score_note=d.get('score',{}).get('toelichting') or 'De score wordt alleen gepubliceerd als alle benodigde bron-KPI’s betrouwbaar beschikbaar zijn.'
    wrap(c,score_note,82,2090,800,15,20,False,'ink',3)
    items=[('Zelfvoorzieningsgraad',d['efficientie'].get('zelfvoorziening'),d['efficientie'].get('delta_zelf'),'blue'),('Eigen verbruik van opwek',d['efficientie'].get('eigen_verbruik'),d['efficientie'].get('delta_eigen'),'green'),('Gasverbruik rapportmaand',d['efficientie'].get('gas'),d['efficientie'].get('delta_gas'),'green')]
    for i,(name,val,delta,col) in enumerate(items):
        y=1718+i*90
        icon(c,'huis' if i==0 else 'balans' if i==1 else 'vlam',1060,y+28,col)
        txt(c,name,1108,y+18,22,True)
        desc=(d['efficientie'].get('model_label') or 'Modelwaarde') if i<2 and d['efficientie'].get('modelled') else ('Volledige PV-bronbalans' if i<2 else 'Vergelijking met dezelfde kalendermaand vorig jaar')
        txt(c,desc,1108,y+48,13,False,'muted')
        if isinstance(val,(int,float)):
            value_text=(f'{val:.1f}%'.replace('.',',') if i<2 else f'{val:.1f} m³'.replace('.',','))
        else:
            value_text='n.b.'
        txt(c,value_text,1905,y+34,34,True,'ink','right')
        delta_text=('modelwaarde' if i<2 and d['efficientie'].get('modelled') else (f'({delta:+.1f}%)'.replace('.',',') if isinstance(delta,(int,float)) else '-'))
        txt(c,delta_text,1905,y+64,15,True,'muted','right')
        c.setFillColor(C['line']); c.roundRect(X(1108),Y(y+82),X(675),20*SY,10*SX,fill=1,stroke=0)
        if isinstance(val,(int,float)):
            scaled=(val/100 if i<2 else min(max(val,0)/20,1))
            c.setFillColor(C[col]); c.roundRect(X(1108),Y(y+82),X(675*scaled),20*SY,10*SX,fill=1,stroke=0)
    rr(c,1045,2010,875,123,16,fill=C['lightgreen'],stroke=C['green'])
    txt(c,'Belangrijkste optimalisatie',1075,2042,18,True)
    wrap(c,'Verschuif vaatwasser, wasmachine en andere flexibele verbruikers naar zonnige uren tussen 11:00 en 16:00. Zelfconsumptie is voor deze maand modelmatig geschat; herijken zodra beide PV-sets volledig bronvast zijn.' if d['efficientie'].get('modelled') else 'Verschuif flexibele verbruikers naar zonnige uren tussen 11:00 en 16:00.',1075,2072,800,13,18,False,'ink',3)

def draw_battery(c,d):
    rr(c,27,2255,620,444,24); rr(c,680,2255,620,444,24); rr(c,1335,2255,623,444,24)
    gauge(c,330,2453,140,d['batterij']['score'],'green'); txt(c,d['batterij']['score'],330,2514,58,True,'green','center'); txt(c,'/100',330,2552,18,True,'ink','center')
    rr(c,83,2585,500,126,18,fill=C['pale'],stroke=C['blue']); txt(c,'Historische referentie - herijking nodig',110,2630,19,True,'ink'); wrap(c,'Laatste batterijmodel is een historische juli-2026 referentie; geen actueel koopadvies totdat prijsprofiel, eigen verbruik en terugverdientijd opnieuw zijn gevalideerd.',110,2660,430,13,18,False,'ink',4)
    txt(c,'Ontwikkeling score',990,2320,23,True,'ink','center'); vals=d['batterij']['ontwikkeling']; pts=[]
    chart_left, chart_right, chart_top, chart_bottom = 748, 1225, 2370, 2555
    # Vaste assen en posities: maanddata veranderen alleen waarden, nooit de template-layout.
    c.setStrokeColor(C['line']); c.setLineWidth(1.5*SX)
    c.line(X(chart_left),Y(chart_top),X(chart_left),Y(chart_bottom))
    c.line(X(chart_left),Y(chart_bottom),X(chart_right),Y(chart_bottom))
    for tick in (40,50,60,70,80):
        ty=chart_bottom-(tick-35)*4.2
        c.setStrokeColor(HexColor('#E4EAF1')); c.line(X(chart_left),Y(ty),X(chart_right),Y(ty))
        txt(c,str(tick),chart_left-16,ty+4,10,False,'muted','right')
    month_labels=['jul 2023','jan 2024','jul 2024','jan 2025','jul 2025','jul 2026']
    for i,v in enumerate(vals):
        x=chart_left+i*((chart_right-chart_left)/(max(1,len(vals)-1)))
        y=chart_bottom-(v-35)*4.2
        pts.append((x,y))
        txt(c,month_labels[i] if i < len(month_labels) else str(i+1),x,chart_bottom+22,10,False,'muted','center')
    c.setStrokeColor(C['green']); c.setLineWidth(3*SX)
    for a,b in zip(pts,pts[1:]): c.line(X(a[0]),Y(a[1]),X(b[0]),Y(b[1]))
    for i,(x,y) in enumerate(pts): c.setFillColor(C['green']); c.circle(X(x),Y(y),7*SX,fill=1,stroke=0); txt(c,str(vals[i]),x,y-16,13,True,'ink','center')
    threshold_y=chart_bottom-(70-35)*4.2
    c.setStrokeColor(C['orange']); c.line(X(chart_left),Y(threshold_y),X(chart_right),Y(threshold_y)); txt(c,'Drempel interessant (>=70)',770,threshold_y-15,12,False,'orange')
    rr(c,735,2580,510,96,14,fill=C['pale'],stroke=C['blue']); txt(c,'Batterijbeoordeling: Marstek Venus 3.0',990,2620,17,True,'ink','center'); txt(c,f"Historisch model t/m juli 2026 - rapportmaand {d['rapport'].get('maand','').lower()}",990,2650,12,False,'muted','center')
    txt(c,'Samenvatting batterij-simulatie',1375,2320,25,True); rows=[('Geschikte capaciteit',d['batterij']['capaciteit']),('Benutting batterij (geschat)',d['batterij']['benutting']),('Jaarlijkse besparing (geschat)',d['batterij']['besparing']),('Investering (plug-in 5 kWh)',d['batterij']['investering']),('Terugverdientijd (huidig)',d['batterij']['terugverdientijd'])]
    for i,(a,b) in enumerate(rows): txt(c,a,1375,2370+i*48,17,False); txt(c,b,1905,2370+i*48,17,True,'ink','right')
    txt(c,'Belangrijkste factoren',1375,2620,20,True)
    for i,s in enumerate(['Saldering loopt verder af richting 2027','Dynamische tarieven bieden kansen','Zelfconsumptie augustus is modelwaarde','Prijs/terugverdientijd opnieuw valideren']): txt(c,'✓',1390,2638+i*24,17,True,'green'); txt(c,s,1420,2638+i*24,15,False)

def generate(data_path:Path,out:Path,assets:Path):
    d=load_and_validate(data_path); out.parent.mkdir(parents=True,exist_ok=True)
    c=canvas.Canvas(str(out),pagesize=A4,pageCompression=1); c.setTitle('Energierapport pagina 1 - maandupdate')
    header(c,d,assets); section(c,1,'MANAGEMENT SAMENVATTING',430,27,572); section(c,2,f"KPI-OVERZICHT - {d['rapport']['maand']}",430,619,1339); draw_summary(c,d); draw_kpis(c,d)
    section(c,3,f"MAANDOVERZICHT - {d['rapport']['maand']}",1080); draw_month(c,d)
    section(c,4,'ENERGIE GEZONDHEIDSSCORE',1620,27,953); section(c,5,'ENERGIE-EFFICIËNTIE & EIGEN VERBRUIK',1620,1005,953); draw_score_eff(c,d)
    section(c,6,'THUISBATTERIJ - IS HET AL INTERESSANT?',2190); draw_battery(c,d)
    txt(c,f"Bronperiode: {d['rapport']['periode']}. Afgeleide KPI's worden alleen getoond bij voldoende bronkwaliteit.",27,2780,12,False,'muted'); txt(c,f"Energierapport - Pagina 1 van {d['rapport']['paginas']}",1958,2780,12,False,'muted','right')
    c.showPage(); c.save()

def main():
    p=argparse.ArgumentParser(); p.add_argument('data',nargs='?',default='maanddata_voorbeeld.json'); p.add_argument('-o','--output',default='output/Energierapport_pagina1.pdf'); a=p.parse_args(); root=Path(__file__).resolve().parent; generate(Path(a.data) if Path(a.data).is_absolute() else root/a.data,Path(a.output) if Path(a.output).is_absolute() else root/a.output,root/'assets')
if __name__=='__main__': main()
