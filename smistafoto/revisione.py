"""Dati per la vista di revisione di un'analisi (la pagina è in web/app.js)."""

from . import VERSIONE


def dati_revisione(lavoro_id, lavoro, prova=None):
    dati = {k: lavoro[k] for k in ("competizione", "evento", "persone", "foto", "volti", "copiato")}
    dati.update(id=lavoro_id, versione=VERSIONE, prova=bool(lavoro.get("prova_su")),
                unica=bool(lavoro.get("unica")), creato=lavoro.get("creato", ""),
                sorgente=lavoro.get("sorgente", ""),
                cartelle_persone=lavoro.get("cartelle_persone", {}))
    prova = prova or {}
    dati["esiti"] = prova.get("esiti")
    dati["regole"] = prova.get("regole") or []
    dati["numeri"] = {k: prova.get(k) for k in ("precisione", "copertura", "giuste", "a_mano",
                                                  "sbagliate", "tra_i_dubbi", "mancate")} if prova else None
    return dati
