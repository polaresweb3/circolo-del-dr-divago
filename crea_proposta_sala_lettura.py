#!/usr/bin/env python3
"""Terza proposta indipendente: la sala di lettura di un circolo letterario."""
from crea_proposta_editoriale import ROOT, book_cards, create

if __name__ == '__main__':
    proposal = ROOT / 'proposte/sala-lettura'
    create(proposal=proposal, source=proposal / 'sorgenti',
           label='PROPOSTA III · SALA DI LETTURA', slug='sala-lettura',
           reference='Biblioteche storiche e circoli letterari; illustrazione originale SVG',
           book_renderer=book_cards, home_page='salotto')
