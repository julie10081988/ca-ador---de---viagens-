#!/usr/bin/env python3
"""Checks an optional authorized JSON feed and sends verified deal alerts."""
import json, os, pathlib, urllib.request, urllib.parse, datetime
ROOT=pathlib.Path(__file__).parent
DATA=ROOT/'offers.json'; STATE=ROOT/'seen.json'
TODAY=datetime.date.today()
def request(url, payload=None, headers=None):
    data=None if payload is None else urllib.parse.urlencode(payload).encode()
    req=urllib.request.Request(url,data=data,headers=headers or {},method='POST' if data else 'GET')
    with urllib.request.urlopen(req,timeout=25) as response: return json.load(response)
def months_ahead(date, n=6):
    y=date.year+(date.month-1+n)//12;m=(date.month-1+n)%12+1
    import calendar
    return datetime.date(y,m,min(date.day,calendar.monthrange(y,m)[1]))
def valid(o):
    try:
        if o['origin'].upper()!='REC' or o.get('international') is not True:return False
        depart=datetime.date.fromisoformat(o['departure']);ret=datetime.date.fromisoformat(o['return'])
        if not(TODAY<=depart<=months_ahead(TODAY) and depart<ret<=months_ahead(TODAY)):return False
        if abs((ret-depart).days-10)>1:return False
        if o['type']=='cash':return 0<float(o['price_brl'])<=4000 and o.get('currency')=='BRL'
        if o['type']=='azul':return int(o['points'])>0 and float(o['taxes_brl'])>=0
        return False
    except (ValueError,TypeError,KeyError):return False
def main():
    feed=os.getenv('FLIGHTS_FEED_URL','').strip()
    token=os.getenv('TELEGRAM_BOT_TOKEN','').strip();chat=os.getenv('TELEGRAM_CHAT_ID','').strip()
    if not feed:
        print('Nenhuma fonte de tarifas conectada. Nenhum alerta enviado.')
        return
    if not feed.startswith('https://'):raise ValueError('A fonte precisa usar HTTPS')
    payload=request(feed,headers={'Authorization':'Bearer '+os.getenv('FLIGHTS_FEED_KEY','')} if os.getenv('FLIGHTS_FEED_KEY') else {})
    if not isinstance(payload,list):raise ValueError('Fonte deve retornar lista JSON')
    seen=set(json.loads(STATE.read_text()) if STATE.exists() else [])
    offers=[];pending=[]
    for o in payload:
        if not isinstance(o,dict) or not valid(o):continue
        key='|'.join(str(o.get(k,'')) for k in ('origin','destination','departure','return','type','price_brl','points','taxes_brl'))
        offers.append(o)
        if key not in seen:pending.append((key,o))
    # The published panel shows verified feed results only, never sample fares.
    DATA.write_text(json.dumps({'checked_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source_connected':True,'offers':offers},ensure_ascii=False,indent=2)+'\n')
    if not(token and chat):
        print('Telegram não configurado. Alertas pendentes:',len(pending));return
    for key,o in pending[:20]:
        price=(f"R$ {float(o['price_brl']):,.2f}" if o['type']=='cash' else f"{int(o['points']):,} pontos Azul + R$ {float(o['taxes_brl']):,.2f} taxas")
        url=o.get('url','')
        msg=f"✈️ Oferta internacional de Recife\n{str(o['destination'])[:60]} | {o['departure']} a {o['return']}\n{price}\n{str(o.get('airline','Companhia não informada'))[:60]}\n{url}"
        request('https://api.telegram.org/bot'+token+'/sendMessage',{'chat_id':chat,'text':msg})
        seen.add(key)
    STATE.write_text(json.dumps(sorted(seen),ensure_ascii=False,indent=2)+'\n')
    print('Ofertas elegíveis:',len(offers),'Alertas enviados:',min(20,len(pending)))
if __name__=='__main__':main()
