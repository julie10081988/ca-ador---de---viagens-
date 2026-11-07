#!/usr/bin/env python3
"""Consulta Google Flights via SerpApi e envia ofertas verificadas ao Telegram."""
import datetime as dt
import json
import os
import pathlib
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent
TODAY = dt.date.today()
DESTINATIONS = [('CUR', 'Curaçao'), ('BKK', 'Bangkok, Tailândia'), ('HKT', 'Phuket, Tailândia'), ('LIS', 'Lisboa'), ('MIA', 'Miami')]


def fetch(url, data=None):
    body = urllib.parse.urlencode(data).encode() if data is not None else None
    with urllib.request.urlopen(url, data=body, timeout=40) as response:
        return json.load(response)


def month_plus(day, months):
    import calendar
    month = day.month - 1 + months
    year = day.year + month // 12
    month = month % 12 + 1
    return dt.date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


def dates_for_run():
    # Uma janela de 10 dias, alternando o mês da viagem a cada execução.
    index = int(TODAY.strftime('%j')) % 5 + 1
    base = month_plus(TODAY, index)
    depart = base + dt.timedelta(days=7)
    end = month_plus(TODAY, 6)
    if depart + dt.timedelta(days=10) > end:
        depart = end - dt.timedelta(days=10)
    return depart, depart + dt.timedelta(days=10)


def main():
    key = os.environ.get('SERPAPI_KEY', '').strip()
    token = os.environ.get('TELEGRAM_BOT_TOKEN', '').strip()
    chat = os.environ.get('TELEGRAM_CHAT_ID', '').strip()
    if not all([key, token, chat]):
        raise RuntimeError('Faltam segredos SERPAPI_KEY, TELEGRAM_BOT_TOKEN ou TELEGRAM_CHAT_ID')
    depart, returning = dates_for_run()
    # Uma consulta por execução para respeitar a franquia gratuita.
    code, name = DESTINATIONS[int(TODAY.strftime('%j')) % len(DESTINATIONS)]
    params = {'engine':'google_flights', 'departure_id':'REC', 'arrival_id':code,
              'outbound_date':depart.isoformat(), 'return_date':returning.isoformat(),
              'type':'1', 'currency':'BRL', 'hl':'pt', 'gl':'br', 'adults':'1', 'api_key':key}
    result = fetch('https://serpapi.com/search.json?' + urllib.parse.urlencode(params))
    if 'error' in result:
        raise RuntimeError('Erro da SerpApi: ' + str(result['error']))
    flights = result.get('best_flights', []) + result.get('other_flights', [])
    eligible = []
    for flight in flights:
        price = flight.get('price')
        if isinstance(price, (int, float)) and 0 < price <= 4000:
            eligible.append(flight)
    offers = []
    for flight in eligible:
        offers.append({'origin':'REC','destination':name,'destination_code':code,
                       'departure':depart.isoformat(),'return':returning.isoformat(),
                       'international':True,'type':'cash','price_brl':flight['price'],
                       'currency':'BRL','airline':', '.join(sorted({leg.get('airline','') for leg in flight.get('flights',[]) if leg.get('airline')})),
                       'url':'https://www.google.com/travel/flights'})
    (ROOT/'offers.json').write_text(json.dumps({'checked_at':dt.datetime.now(dt.timezone.utc).isoformat(),
         'source_connected':True,'offers':offers}, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    # Não afirmamos que tarifa em cache é reserva garantida.
    state = ROOT/'seen.json'
    seen = set(json.loads(state.read_text(encoding='utf-8'))) if state.exists() else set()
    sent = 0
    for offer in offers:
        identifier = '|'.join(str(offer[k]) for k in ('destination_code','departure','return','price_brl'))
        if identifier in seen: continue
        message = (f"✈️ Caçador de Viagens — tarifa encontrada\nREC ↔ {name}\n"
                   f"{depart:%d/%m/%Y} a {returning:%d/%m/%Y}\n"
                   f"R$ {offer['price_brl']:,.0f} ida e volta por pessoa\n"
                   "Preço sujeito a alteração. Confira no Google Flights antes de comprar.\n"
                   "https://www.google.com/travel/flights")
        response = fetch('https://api.telegram.org/bot'+token+'/sendMessage', {'chat_id':chat,'text':message})
        if not response.get('ok'): raise RuntimeError('Telegram não confirmou envio')
        seen.add(identifier)
        sent += 1
    state.write_text(json.dumps(sorted(seen), ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(f'Consulta concluída: REC-{code}, {depart} a {returning}, {len(flights)} itinerários, {sent} alertas.')

if __name__ == '__main__':
    main()
