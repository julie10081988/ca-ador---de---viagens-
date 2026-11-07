#!/usr/bin/env python3
"""Monitor de tarifas internacionais REC via SerpApi / Google Flights."""
import calendar
import datetime as dt
import json
import os
from pathlib import Path
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parent
TODAY = dt.date.today()
LIMIT = 4000
DESTINATIONS = [
    ('CUR', 'Curaçao', 3), ('BKK', 'Bangkok, Tailândia', 3),
    ('HKT', 'Phuket, Tailândia', 2), ('LIS', 'Lisboa', 1),
    ('MIA', 'Miami', 1), ('MAD', 'Madri', 1), ('CDG', 'Paris', 1),
    ('FCO', 'Roma', 1), ('BOG', 'Bogotá', 1), ('SCL', 'Santiago', 1),
    ('EZE', 'Buenos Aires', 1), ('JFK', 'Nova York', 1),
]


def load_json(path, default):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return default


def save_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def add_months(day, months):
    m = day.month - 1 + months
    year, month = day.year + m // 12, m % 12 + 1
    return dt.date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


def get_json(url, payload=None):
    body = urllib.parse.urlencode(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=body, headers={'User-Agent': 'CacadorViagens/1.0'})
    with urllib.request.urlopen(req, timeout=45) as response:
        return json.load(response)


def choose_search(state):
    # Persistent rotation: each run changes destination and departure window.
    # 12 queries/day = ~360/month; default 6/day = ~180/month.
    rotation = [item for item in DESTINATIONS for _ in range(item[2])]
    index = int(state.get('search_count', 0))
    code, name, _ = rotation[index % len(rotation)]
    # Cycle through 6 months and 3 departure offsets, without changing 10-day stay.
    window = (index // len(rotation)) % 18
    month_offset = 1 + window % 6
    day_offset = (window // 6) * 7
    depart = add_months(TODAY, month_offset) + dt.timedelta(days=day_offset)
    return code, name, depart, depart + dt.timedelta(days=10)


def main():
    key = os.getenv('SERPAPI_KEY', '').strip()
    token = os.getenv('TELEGRAM_BOT_TOKEN', '').strip()
    chat = os.getenv('TELEGRAM_CHAT_ID', '').strip()
    if not all((key, token, chat)):
        raise RuntimeError('Configure SERPAPI_KEY, TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID nos Secrets.')

    state_path = ROOT / 'search_state.json'
    state = load_json(state_path, {})
    code, name, depart, returning = choose_search(state)
    params = {
        'engine': 'google_flights', 'departure_id': 'REC', 'arrival_id': code,
        'outbound_date': depart.isoformat(), 'return_date': returning.isoformat(),
        'type': '1', 'currency': 'BRL', 'hl': 'pt', 'gl': 'br',
        'adults': '1', 'api_key': key,
    }
    result = get_json('https://serpapi.com/search.json?' + urllib.parse.urlencode(params))
    if result.get('error'):
        raise RuntimeError('Erro SerpApi: ' + str(result['error']))
    flights = result.get('best_flights', []) + result.get('other_flights', [])
    offers = []
    for flight in flights:
        price = flight.get('price')
        if isinstance(price, (int, float)) and not isinstance(price, bool) and 0 < price <= LIMIT:
            offers.append({
                'origin': 'REC', 'destination': name, 'destination_code': code,
                'departure': depart.isoformat(), 'return': returning.isoformat(),
                'international': True, 'type': 'cash', 'price_brl': price,
                'currency': 'BRL', 'airline': ', '.join(sorted({leg.get('airline', '')
                    for leg in flight.get('flights', []) if leg.get('airline')})),
                'url': 'https://www.google.com/travel/flights',
            })

    checked = dt.datetime.now(dt.timezone.utc).isoformat()
    history_path = ROOT / 'history.json'
    history = load_json(history_path, [])
    history.extend([{**offer, 'checked_at': checked} for offer in offers])
    save_json(history_path, history[-300:])
    save_json(ROOT / 'offers.json', {
        'checked_at': checked, 'source_connected': True,
        'last_search': {'destination': name, 'departure': depart.isoformat(),
                        'return': returning.isoformat(), 'itineraries': len(flights)},
        'offers': offers,
    })

    seen_path = ROOT / 'seen.json'
    seen = set(load_json(seen_path, []))
    sent = 0
    for offer in offers:
        identifier = '|'.join(str(offer[k]) for k in
                              ('destination_code', 'departure', 'return', 'price_brl'))
        if identifier in seen:
            continue
        priority = '⭐ DESTINO PRIORITÁRIO\n' if code in ('CUR', 'BKK', 'HKT') else ''
        message = (f'✈️ Caçador de Viagens\n{priority}REC ↔ {name}\n'
                   f'{depart:%d/%m/%Y} a {returning:%d/%m/%Y}\n'
                   f'R$ {offer["price_brl"]:,.0f} ida e volta por pessoa\n'
                   'Preço sujeito a alteração; confirme antes de comprar.\n'
                   'https://www.google.com/travel/flights')
        response = get_json('https://api.telegram.org/bot' + token + '/sendMessage',
                            {'chat_id': chat, 'text': message})
        if not response.get('ok'):
            raise RuntimeError('Telegram não confirmou o envio.')
        seen.add(identifier)
        save_json(seen_path, sorted(seen))
        sent += 1

    state['search_count'] = int(state.get('search_count', 0)) + 1
    save_json(state_path, state)
    print(f'Consulta concluída: REC-{code}, {depart} a {returning}, '
          f'{len(flights)} itinerários, {len(offers)} ofertas elegíveis, {sent} alertas.')


if __name__ == '__main__':
    if os.getenv('TESTE_TELEGRAM') == '1':
        token = os.environ['TELEGRAM_BOT_TOKEN']
        chat = os.environ['TELEGRAM_CHAT_ID']
        resposta = fetch(
            'https://api.telegram.org/bot' + token + '/sendMessage',
            {
                'chat_id': chat,
                'text': '✈️ Teste do Caçador de Viagens! Telegram conectado com sucesso.'
            }
        )
        print('Teste Telegram:', resposta.get('ok'))
    else:
        main()
