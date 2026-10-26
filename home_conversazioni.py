"""Le conversazioni scelte per l’ingresso del Circolo, dai dati del catalogo."""
from html import escape

SELECTION = (
    {'id': 'HXgpLjZ7apA', 'start': 0, 'label': 'PER CONOSCERE IL CANALE',
     'description': 'Perché condividere le letture e le idee? Dr Divago racconta le ragioni del canale e il senso delle sue conversazioni.'},
    {'id': 'vj1E4hCrITY', 'start': 260, 'label': 'UN PERCORSO DI LETTURA',
     'description': 'Utopie, distopie e libertà di pensiero: un percorso tra i libri che precedono e accompagnano George Orwell.'},
)


def clock(seconds):
    hours, rest = divmod(seconds, 3600)
    minutes, seconds = divmod(rest, 60)
    return f'{hours}:{minutes:02}:{seconds:02}' if hours else f'{minutes}:{seconds:02}'


def home_conversations(videos):
    lookup = {video['id']: video for video in videos}
    cards = []
    for index, selection in enumerate(SELECTION):
        ident, start = selection['id'], selection['start']
        if ident not in lookup:
            raise ValueError('Conversazione scelta per la Home assente dal catalogo: ' + ident)
        video = lookup[ident]
        title, duration = video.get('title'), video.get('duration')
        if not isinstance(title, str) or not title.strip() or type(duration) is not int or duration <= start:
            raise ValueError('Titolo o durata non validi per la conversazione in Home: ' + ident)
        target = 'video/' + ident + '.html' + (f'?t={start}' if start else '')
        action = 'Guarda il video'
        accessible = escape(action + ': ' + title, quote=True)
        priority = ' fetchpriority="high"' if index == 0 else ''
        cards.append(
            f'<article class="home-conversation" aria-labelledby="home-video-{ident}">'
            f'<a class="thumbnail-button" href="{escape(target, quote=True)}" aria-label="{accessible}">'
            f'<img src="https://i.ytimg.com/vi/{ident}/hqdefault.jpg" alt="" width="480" height="270" loading="eager" decoding="async"{priority}>'
            f'<span class="play-icon" aria-hidden="true">▶</span><span class="duration">{clock(duration)}</span></a>'
            f'<p class="eyebrow home-conversation-label">{selection["label"]}</p>'
            f'<h2 id="home-video-{ident}"><a href="{escape(target, quote=True)}">{escape(title)}</a></h2>'
            f'<p class="home-conversation-description">{escape(selection["description"])}</p>'
            f'<div class="home-conversation-actions"><a class="button" href="{escape(target, quote=True)}">{action} <span aria-hidden="true">→</span></a></div></article>')
    return '<div class="home-conversations">' + ''.join(cards) + '</div>'
