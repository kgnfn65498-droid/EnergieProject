from __future__ import annotations
import json, math, argparse
from pathlib import Path
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.colors import HexColor, white
from reportlab.pdfbase.pdfmetrics import stringWidth

W,H=A4
NAVY=HexColor('#0b3767'); BLUE=HexColor('#0c447d'); PALE=HexColor('#edf3fa'); BORDER=HexColor('#cbd8e6')
TEXT=HexColor('#102d50'); GREEN=HexColor('#159447'); ORANGE=HexColor('#f39200'); GRAY=HexColor('#6f7f91'); LGRAY=HexColor('#f3f6fa')
M=22

def txt(c,x,y,s,size=8,bold=False,color=TEXT,align='left'):
    c.setFillColor(color); c.setFont('Helvetica-Bold' if bold else 'Helvetica',size)
    if align=='center': c.drawCentredString(x,y,s)
    elif align=='right': c.drawRightString(x,y,s)
    else: c.drawString(x,y,s)

def wrap(c,text,x,y,width,size=8,leading=10,bold=False,color=TEXT,max_lines=None):
    words=str(text).split(); lines=[]; line=''
    font='Helvetica-Bold' if bold else 'Helvetica'
    for w in words:
        trial=(line+' '+w).strip()
        if stringWidth(trial,font,size)<=width: line=trial
        else:
            if line: lines.append(line)
            line=w
    if line: lines.append(line)
    if max_lines: lines=lines[:max_lines]
    for i,ln in enumerate(lines): txt(c,x,y-i*leading,ln,size,bold,color)
    return y-len(lines)*leading

def rounded(c,x,y,w,h,fill=white,stroke=BORDER,r=7,lw=.8):
    c.setLineWidth(lw); c.setStrokeColor(stroke); c.setFillColor(fill); c.roundRect(x,y,w,h,r,fill=1,stroke=1)

def header(c,page,title,status):
    c.setFillColor(NAVY); c.rect(0,H-26,W,26,fill=1,stroke=0)
    txt(c,M,H-17,status,6.5,True,white); txt(c,W-M,H-17,f'Pagina {page}',6.5,True,white,'right')
    txt(c,M,H-52,title,16,True,TEXT)

def footer(c): txt(c,W-18,12,'©',5,False,GRAY,'right')

def section_bar(c,x,y,w,label):
    c.setFillColor(NAVY); c.roundRect(x,y,w,19,6,fill=1,stroke=0); txt(c,x+10,y+5,label,9,True,white)

def table(c,x,y,w,headers,rows,col_fracs=None,row_h=28,font=7):
    n=len(headers); col_fracs=col_fracs or [1/n]*n; widths=[w*f for f in col_fracs]
    c.setFillColor(NAVY); c.rect(x,y-row_h,w,row_h,fill=1,stroke=0)
    cx=x
    for i,h in enumerate(headers): txt(c,cx+8,y-row_h+9,h,font,True,white); cx+=widths[i]
    yy=y-row_h
    for r,row in enumerate(rows):
        yy-=row_h; c.setFillColor(LGRAY if r%2 else white); c.rect(x,yy,w,row_h,fill=1,stroke=0)
        cx=x
        for i,val in enumerate(row): wrap(c,str(val),cx+8,yy+row_h-11,widths[i]-12,font,8,max_lines=2); cx+=widths[i]
    return yy

def callout(c,x,y,w,h,title,body,kind='info'):
    fill=PALE if kind=='info' else HexColor('#fff7e7'); stroke=HexColor('#9cb9d6') if kind=='info' else ORANGE
    rounded(c,x,y,w,h,fill,stroke,7)
    c.setFillColor(NAVY if kind=='info' else ORANGE); c.circle(x+18,y+h-21,12,fill=1,stroke=0)
    txt(c,x+18,y+h-24,'i' if kind=='info' else '!',9,True,white,'center')
    txt(c,x+40,y+h-22,title,8,True,TEXT if kind=='info' else ORANGE)
    wrap(c,body,x+40,y+h-38,w-52,7.2,9)

def kpi_card(c,x,y,w,h,value,label,sub):
    rounded(c,x,y,w,h)
    txt(c,x+w/2,y+h-30,value,14,True,TEXT,'center'); txt(c,x+w/2,y+h-63,label,7,True,TEXT,'center'); txt(c,x+w/2,y+10,sub,6,False,GRAY,'center')

def line_chart(c,x,y,w,h,series,labels=None,colors=None,ymax=None,title=None,legend=None):
    colors=colors or [BLUE,GREEN,ORANGE]
    if title: txt(c,x,y+h+10,title,8,True)
    left=28; bottom=18
    vals=[v for s in series for v in s]; ymax=ymax or max(vals)*1.1 or 1
    c.setStrokeColor(BORDER); c.setLineWidth(.5)
    for i in range(5):
        yy=y+bottom+(h-bottom-8)*i/4; c.line(x+left,yy,x+w-5,yy); txt(c,x+left-5,yy-2,f'{int(ymax*i/4)}',5,False,GRAY,'right')
    c.line(x+left,y+bottom,x+left,y+h-8); c.line(x+left,y+bottom,x+w-5,y+bottom)
    n=max(len(s) for s in series)
    if labels:
        for i,l in enumerate(labels):
            if i%max(1,len(labels)//8)==0: txt(c,x+left+(w-left-8)*i/(n-1),y+5,l,5,False,GRAY,'center')
    for si,s in enumerate(series):
        c.setStrokeColor(colors[si]); c.setFillColor(colors[si]); c.setLineWidth(1.5)
        pts=[]
        for i,v in enumerate(s):
            px=x+left+(w-left-8)*i/(len(s)-1); py=y+bottom+(h-bottom-8)*v/ymax; pts.append((px,py))
        for a,b in zip(pts,pts[1:]): c.line(a[0],a[1],b[0],b[1])
        for px,py in pts: c.circle(px,py,1.8,fill=1,stroke=0)
    if legend:
        lx=x+left
        for i,l in enumerate(legend): c.setFillColor(colors[i]); c.rect(lx,y+h-2,7,7,fill=1,stroke=0); txt(c,lx+11,y+h,l,5.5); lx+=90

def bar_chart(c,x,y,w,h,a,b,labels,title):
    txt(c,x,y+h+10,title,8,True); left=28; bottom=20; ymax=max(max(a),max(b))*1.15
    for i in range(6):
        yy=y+bottom+(h-bottom-8)*i/5; c.setStrokeColor(BORDER); c.line(x+left,yy,x+w-4,yy); txt(c,x+left-5,yy-2,str(int(ymax*i/5)),5,False,GRAY,'right')
    n=len(a); step=(w-left-8)/n; bw=step*.28
    for i,(va,vb) in enumerate(zip(a,b)):
        px=x+left+i*step+step*.15
        c.setFillColor(BLUE); c.rect(px,y+bottom,bw,(h-bottom-8)*va/ymax,fill=1,stroke=0)
        c.setFillColor(GREEN); c.rect(px+bw+1,y+bottom,bw,(h-bottom-8)*vb/ymax,fill=1,stroke=0)
        txt(c,px+bw,y+7,labels[i],4.7,False,GRAY,'center')
    c.setFillColor(BLUE); c.rect(x+40,y+h-2,8,8,fill=1,stroke=0); txt(c,x+52,y+h,'Netafname (kWh)',5.5)
    c.setFillColor(GREEN); c.rect(x+145,y+h-2,8,8,fill=1,stroke=0); txt(c,x+157,y+h,'Teruglevering (kWh)',5.5)

def donut(c,cx,cy,r,part,total,colors=(HexColor('#31a6bf'),HexColor('#58ae3e'))):
    # draw full ring then overlay first segment
    c.setLineWidth(15); c.setStrokeColor(colors[1]); c.circle(cx,cy,r,fill=0,stroke=1)
    if total>0:
        c.setStrokeColor(colors[0]); c.setLineWidth(15)
        start=90; extent=360*part/total
        c.arc(cx-r,cy-r,cx+r,cy+r,start,start+extent)

def page3(c,d):
    header(c,3,f"2. Dashboard - {d['meta']['month']}",d['meta']['status'])
    vals=[(f"{d['dashboard']['house']} kWh",'Totaal huisverbruik',f"{d['meta']['days']} dagen"),(f"{d['dashboard']['solar']} kWh",'Zonneproductie',f"{d['meta']['days']} dagen"),(f"{d['dashboard']['self']:.1f} %".replace('.',','),'Zelfconsumptie','Onderzoeken'),(f"{d['dashboard']['export']} kWh",'Netto export','voorlopig')]
    x=M; gap=12; cw=(W-2*M-3*gap)/4
    for i,v in enumerate(vals): kpi_card(c,x+i*(cw+gap),H-175,cw,78,*v)
    rounded(c,M,H-280,W-2*M,82)
    txt(c,M+20,H-220,'Totaalscore energieprofiel',8,True); txt(c,W/2,H-262,f"{d['dashboard']['score']}/100",13,True,TEXT,'center'); txt(c,W/2,H-286,f"Datakwaliteit: {d['dashboard']['quality']}",7,True,TEXT,'center')
    rows=[['Elektriciteitsverbruik','90','Goed','Stabiel zomerprofiel'],['Zonnepanelen','94','Goed','Hoge productie, veel export'],['Zelfconsumptie','64','Aandacht','Slechts 18,8% direct gebruikt'],['Gas','96','Goed','Laag zomerverbruik'],['Apparaten','92','Goed','Geen opvallende uitschieter'],['Financieel','82','Goed','Export drukt variabele kosten'],['Datakwaliteit','55','Simulatie','Geen echte kwartier- of apparaatdata'],['Totaal','91','Goed','Geen directe ingreep nodig']]
    table(c,M,H-310,W-2*M,['Onderdeel','Score','Status','Kernpunt'],rows,[.36,.11,.16,.37],30,7)
    wrap(c,'Leeswijzer: de totaalscore is inhoudelijk, maar de datakwaliteit blijft bewust laag omdat de bronwaarden deels zijn verzonnen. Bij de echte maandupdate vervalt deze beperking.',M,32,W-2*M,6.5,8,True)
    footer(c)

def page4(c,d):
    header(c,4,'3. Simulatiebasis en aannames',d['meta']['status'])
    wrap(c,'De netafname en teruglevering zijn overgenomen uit juli 2025. De overige waarden zijn zo gekozen dat zij onderling rekenkundig aansluiten en passen bij de bekende woning, zonnepanelen, airco en sockets.',M,H-90,W-2*M,8.3,11,True)
    rows=[['Netafname',f"{d['electricity']['grid']} kWh",'Beschikbare periode'],['Teruglevering',f"{d['electricity']['feedin']} kWh",'Beschikbare periode'],['Zonneproductie',f"{d['solar']['production']} kWh",'Enphase export'],['Direct gebruikte zonnestroom',f"{d['solar']['direct']} kWh",'Productie minus teruglevering'],['Totaal huishoudelijk gebruik',f"{d['electricity']['house']} kWh",'Netafname plus directe zonnestroom'],['Gas',f"{d['gas']['month']} m³",'HomeWizard gas'],['Dynamische tarieven','Werkelijk','EPEX gekoppeld']]
    table(c,M,H-145,W-2*M,['Waarde','Maanddata','Herkomst / reden'],rows,[.38,.20,.42],38,8)
    callout(c,M,110,W-2*M,95,'Controleformule',f"{d['solar']['production']} kWh productie - {d['electricity']['feedin']} kWh teruglevering = {d['solar']['direct']} kWh direct gebruikt. {d['electricity']['grid']} kWh netafname + {d['solar']['direct']} kWh direct gebruikt = {d['electricity']['house']} kWh totaal huishoudelijk verbruik.")
    footer(c)

def page5(c,d):
    header(c,5,'4. Elektriciteitsanalyse',d['meta']['status'])
    wrap(c,f"De beschikbare juliwaarde past in het zomerprofiel. De woning neemt {d['electricity']['grid']} kWh van het net af en levert {d['electricity']['feedin']} kWh terug. Per saldo is de woning {abs(d['electricity']['net'])} kWh netto-exporteur.",M,H-90,W-2*M,8.3,11,True)
    rows=[['Netafname',f"{d['electricity']['grid']} kWh",'Voorlopig'],['Teruglevering',f"{d['electricity']['feedin']} kWh",'Hoge zomerexport'],['Netto netpositie',f"{d['electricity']['net']} kWh",'Netto-export'],['Gemiddelde netafname per dag',f"{d['electricity']['grid_day']} kWh",'Voorlopig'],['Gemiddelde teruglevering per dag',f"{d['electricity']['feedin_day']} kWh",'Hoog'],['Totaal huisverbruik',f"{d['electricity']['house']} kWh",f"{d['electricity']['house']/d['meta']['days']:.1f} kWh per dag"]]
    table(c,M,H-145,W-2*M,['KPI','Waarde','Beoordeling'],rows,[.40,.20,.40],34,8)
    rounded(c,M,40,W-2*M,300)
    bar_chart(c,M+25,65,W-2*M-50,235,d['electricity']['daily_grid'],d['electricity']['daily_feed'],[str(i) for i in range(1,32)],f"Netafname en teruglevering - {d['meta']['month']} (per dag)")
    footer(c)

def page6(c,d):
    header(c,6,'5. Zonnepanelen en zelfconsumptie',d['meta']['status'])
    wrap(c,f"Van de productie van {d['solar']['production']} kWh wordt circa {d['solar']['direct']} kWh direct in huis gebruikt. Dat is {d['solar']['self']:.1f}% van de productie. De zonnepanelen dekken daarmee {d['solar']['coverage']:.1f}% van het huishoudelijke verbruik direct, zonder tussenkomst van het net.",M,H-90,W-2*M,8.3,11,True)
    rounded(c,M,190,230,390); txt(c,M+18,548,'Verdeling zonnestroom',8,True)
    donut(c,M+115,405,70,d['solar']['direct'],d['solar']['production']); txt(c,M+115,403,f"{d['solar']['production']} kWh",12,True,TEXT,'center'); txt(c,M+115,387,'productie',6,False,GRAY,'center')
    txt(c,M+24,255,f"■  Direct eigen gebruik: {d['solar']['direct']} kWh ({d['solar']['self']:.1f}%)",6.7,False,HexColor('#31a6bf'))
    txt(c,M+24,230,f"■  Teruglevering: {d['solar']['feedin']} kWh ({100-d['solar']['self']:.1f}%)",6.7,False,HexColor('#58ae3e'))
    rows=[['Productie',f"{d['solar']['production']} kWh",'Sterke julimaand'],['Direct eigen gebruik',f"{d['solar']['direct']} kWh",'Verbeterbaar'],['Teruglevering',f"{d['solar']['feedin']} kWh",f"{100-d['solar']['self']:.1f}% van productie"],['Zelfconsumptie',f"{d['solar']['self']:.1f}%",'Laag, normaal zonder batterij/EV'],['Directe zonnedekking woning',f"{d['solar']['coverage']:.1f}%",'Redelijk']]
    table(c,275,585,W-297,['Indicator','Waarde','Interpretatie'],rows,[.40,.25,.35],45,7.4)
    callout(c,M,45,W-2*M,82,'Aanbeveling','Verplaats alleen eenvoudig verschuifbaar verbruik naar 11:00-16:00. Apparaten expres extra laten draaien om teruglevering te vermijden is meestal geen besparing.')
    footer(c)

def page7(c,d):
    header(c,7,'6. Apparaten, airco en heaters',d['meta']['status'])
    rows=[['Airco woonkamer','8,6','Beperkt koelen','Geen actie'],['Heater woonkamer','0,4','Stand-by/test','Geen actie'],['Heater kantoor','0,3','Stand-by/test','Geen actie'],['Heater lounge','0,2','Stand-by/test','Geen actie'],['Koelkast/vriezer woonkamer','34,0','Normaal','Geen actie'],['Koelkast keuken','27,0','Normaal','Geen actie'],['Diepvries garage','29,0','Normaal','Geen actie'],['Koelkast lounge','18,0','Normaal zomergebruik','Geen actie'],['Overig huishouden','225,5','Restpost','Volgen']]
    table(c,M,H-90,W-2*M,['Apparaat','kWh','Status','Beoordeling'],rows,[.38,.12,.25,.25],42,8)
    callout(c,M,90,W-2*M,100,'Toelichting','De drie heaters zijn met een minimale waarde opgenomen: samen 0,9 kWh. Dit stelt stand-byverbruik en een korte test voor, niet werkelijk verwarmingsgebruik. De airco is met 8,6 kWh beperkt gebruikt voor koeling.')
    footer(c)

def page8(c,d):
    header(c,8,'7. Gasanalyse',d['meta']['status'])
    vals=[(f"{d['gas']['month']} m³",'Gas maand',f"{d['meta']['days']} dagen"),(f"{d['gas']['per_day']} m³",'Per dag','gemiddeld'),(f"{d['gas']['reference']} m³",'Jaarreferentie','bekend')]
    cw=(W-2*M-20)/3
    for i,v in enumerate(vals): kpi_card(c,M+i*(cw+10),H-180,cw,85,*v)
    rounded(c,M,250,W-2*M,330)
    line_chart(c,M+20,285,W-2*M-40,240,[d['gas']['history']],['aug22','okt22','dec22','feb23','apr23','jun23','aug23','okt23','dec23','feb24','apr24','jun24'],[GREEN],350,'Gasverbruik per meetmoment',['Gasverbruik (m³)'])
    callout(c,M,65,W-2*M,90,'Conclusie','Zeer laag gasverbruik voor de zomer. Verwarming staat vrijwel uit. Verbruik komt overeen met warm water en koken.')
    footer(c)

def page9(c,d):
    header(c,9,'8. Financiën en leverancierscontrole',d['meta']['status'])
    wrap(c,'De tarieven hieronder dienen als rapportcontrole. De echte maandupdate gebruikt werkelijke uurprijzen, vaste kosten, belastingen en netbeheerkosten.',M,H-90,W-2*M,8.3,11,True)
    table(c,M,H-135,W-2*M,['Post','Berekening','Bedrag'],d['finance']['rows'],[.35,.40,.25],36,7.5)
    kpi_card(c,M,345,250,95,f"€ {d['finance']['energy_cost']:.2f}".replace('.',','),'Indicatieve energiekosten',f"{d['meta']['days']} beschikbare dagen")
    kpi_card(c,M+270,345,250,95,f"€ {d['finance']['term']:.2f}".replace('.',','),'Huidige maandtermijn','per maand')
    rows=[['Factuurperiode','Nog niet volledig gecontroleerd'],['Meterstanden begin/eind','Worden in maandupdate aangesloten'],['Dynamische uurprijzen','EPEX gekoppeld'],['Vaste leveringskosten','Opgenomen'],['Netbeheerkosten','Uitgesplitst'],['Eindoordeel','Nog geen leveranciersafwijking vast te stellen']]
    table(c,M,315,W-2*M,['Controlepunt','Status'],rows,[.42,.58],32,7.5)
    callout(c,M,55,W-2*M,82,'Interpretatie','Bij de definitieve maandupdate worden begin- en eindstanden, uurprijzen, vaste kosten en netbeheerkosten volledig op elkaar aangesloten.')
    footer(c)

def page10(c,d):
    header(c,10,'9. Voortschrijdende jaarprognose',d['meta']['status'])
    wrap(c,'Omdat alleen juli beschikbaar is, blijft de bekende jaarreferentie leidend. De proefberekening laat zien welke prognoses straks automatisch worden bijgewerkt.',M,H-90,W-2*M,8.3,11,True)
    table(c,M,H-145,W-2*M,['Jaar-KPI','Referentie','Proefprognose','Signaal'],d['forecast']['rows'],[.30,.22,.25,.23],42,7.5)
    txt(c,M,H-395,'Historische contractjaren',10,True)
    hist=[['15-07-2022 → 15-07-2023','3.791 kWh','1.838 kWh','≈ 1.302 m³'],['15-07-2023 → 15-07-2024','3.813 kWh','2.628 kWh','1.058 m³'],['15-07-2024 → 15-07-2025','4.886 kWh','4.309 kWh','699 m³'],['15-07-2025 → 15-07-2026','4.958 kWh','4.316 kWh','705 m³']]
    table(c,M,H-410,W-2*M,['Contractjaar','Verbruik','Teruglevering','Gas'],hist,[.34,.22,.22,.22],48,7.5)
    callout(c,M,45,W-2*M,75,'Interpretatie','Elektriciteitsverbruik is de laatste twee contractjaren duidelijk hoger dan in 2022-2024. Teruglevering is sterk gestegen door de nieuwe zonnepanelen. Gas ligt sinds 2024 rond 700 m³ per jaar.')
    footer(c)

def page11(c,d):
    header(c,11,'10. Thuisbatterij - scenarioanalyse',d['meta']['status'])
    wrap(c,'Het profiel is technisch aantrekkelijk: veel teruglevering overdag en tegelijk netafname op andere momenten. De financiële uitkomst hangt af van prijsverschillen, laadverliezen en het werkelijk verschuifbare volume.',M,H-90,W-2*M,8.3,11,True)
    table(c,M,H-145,W-2*M,['Scenario','Configuratie','Verschuifbaar','Waarde','Beoordeling'],d['battery']['rows'],[.16,.25,.18,.18,.23],48,7.2)
    rows=[['Kandidaat','Marstek Venus 5,1 kWh, plug-in'],['Standaard ontlaadvermogen','800 W'],['Indicatieve jaarwaarde','circa € 103'],['Aankoopprijs rekenvoorbeeld','€ 1.200'],['Ruwe terugverdientijd','circa 11,6 jaar'],['Oordeel','Volgen, nog geen koopadvies']]
    table(c,M,H-410,W-2*M,['Onderdeel','Indicatie'],rows,[.43,.57],36,7.5)
    callout(c,M,55,W-2*M,100,'Voorlopige conclusie','De batterij kan het zelfverbruik duidelijk verhogen, maar met deze prijsverschillen is het financiële voordeel nog onvoldoende overtuigend. Bij negatieve terugleverprijzen of een lagere aankoopprijs kan dit snel veranderen.','warn')
    footer(c)

def page12(c,d):
    header(c,12,'11. Aanbevelingen en actiepunten',d['meta']['status'])
    rows=[['Nu','Geen aankoopbesluit nemen','Rapportperiode is nog onvolledig'],['Begin augustus','Echte juli-data verwerken','Vervangt alle voorlopige waarden'],['Na echte import','Controleer kwartieroverschotten','Bepaalt batterijpotentieel'],['Na 3 maanden','Vergelijk zelfconsumptie en dynamische prijzen','Voorkomt conclusie op één zomermaand'],['Voor winter','Controleer heaters per socket','Herken efficiëntie en ongewenst gebruik'],['Bij prijsdaling batterij','Nieuwe businesscase Marstek uitvoeren','Prijs bepaalt terugverdientijd']]
    table(c,M,H-90,W-2*M,['Moment','Actie','Waarom'],rows,[.20,.42,.38],44,7.5)
    txt(c,M,H-405,'Prioriteitenvolgorde',10,True)
    items=['Echte juli-data importeren','Kwartieroverschotten bepalen','Dynamische prijsuren koppelen','Zelfconsumptie en batterij simuleren','Na meerdere maanden pas beslissen']
    for i,it in enumerate(items):
        c.setFillColor(NAVY); c.circle(M+12,H-440-i*38,10,fill=1,stroke=0); txt(c,M+12,H-443-i*38,str(i+1),7,True,white,'center'); txt(c,M+32,H-444-i*38,it,8,True)
    callout(c,M,45,W-2*M,78,'Standaard workflow','Gebruik bij nieuwe maanddata eerst "Verwerk de maandupdate". Gebruik daarna "Maak een complete backup" om ook een nieuwe Recovery Package te genereren.')
    footer(c)

def page13(c,d):
    header(c,13,'12. Datakwaliteit en broncontrole',d['meta']['status'])
    wrap(c,'In het echte maandrapport krijgt iedere bron een controle op volledigheid, periode, resolutie, dubbele regels en aansluiting op meterstanden. Deze pagina toont de vaste controlevorm.',M,H-90,W-2*M,8.3,11,True)
    rows=[['HomeWizard P1 stroom','Maandtotaal afgeleid','15-minutenexport'],['HomeWizard gas','Maandtotaal gemeten','15-minutenexport'],['Enphase','Productie gemeten','Aangepaste export uit Energie-menu'],['Sockets','Aanwezige exports','Export per vaste socket'],['SlimmeMeterPortal','Controlebron','Jaarhistorie indien nodig'],['Contractprijzen','Werkelijke data','EPEX uurprijzen en kosten']]
    table(c,M,H-140,W-2*M,['Bron','In huidige rapportage','Definitieve bron'],rows,[.30,.30,.40],38,7.5)
    txt(c,M,H-415,'Controlepunten echte maandupdate',10,True)
    checks=['Volledige vorige kalendermaand aanwezig','Alle timestamps in dezelfde tijdzone','Geen dubbele kwartierregels','Aansluiting P1-totalen op meterstanden','Enphase-productie via Aangepaste export','Socketnamen en apparaatkoppelingen ongewijzigd','Contractprijzen en vaste kosten actueel','Afwijkingen automatisch gemarkeerd']
    for i,ch in enumerate(checks):
        yy=H-448-i*28; c.setFillColor(GREEN); c.circle(M+8,yy+2,7,fill=1,stroke=0); txt(c,M+8,yy-1,'✓',7,True,white,'center'); txt(c,M+24,yy-1,ch,7.7)
    callout(c,M,45,W-2*M,88,'Definitieve status','Rapportopzet geschikt. Dashboard, apparaten, financiële controle, voortschrijdende jaarprognose, batterijscenario’s, aanbevelingen en datakwaliteit zijn opgenomen.')
    footer(c)

def generate(data_path,out_path):
    d=json.loads(Path(data_path).read_text(encoding='utf-8'))
    c=canvas.Canvas(str(out_path),pagesize=A4)
    for fn in (page3,page4,page5,page6,page7,page8,page9,page10,page11,page12,page13): fn(c,d); c.showPage()
    c.save()

if __name__=='__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('--data',default=str(Path(__file__).parents[1]/'data/juli_2026.json')); ap.add_argument('--output',default=str(Path(__file__).parents[1]/'output/Energierapport_Pagina3_tm_13_voorbeeld_v1.pdf')); a=ap.parse_args(); generate(a.data,a.output)
