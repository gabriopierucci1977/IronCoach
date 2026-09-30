# Principio di prodotto: coaching personale basato sull’IA

Stato: **requisito di prodotto e di architettura per gli sviluppi successivi**.

## Identità del prodotto

IronCoach è un coach personale basato sull’intelligenza artificiale. In questa
fase serve un solo utilizzatore, che coincide con l’unico atleta configurato.
Il prodotto integra la storia di allenamento dell’atleta e usa l’IA come
componente centrale per:

- analizzare nel tempo allenamenti, risultati e risposte dichiarate;
- spiegare feedback e conclusioni in modo comprensibile;
- proporre piani orientati a una gara e agli obiettivi dell’atleta;
- rivedere quei piani sulla base dei risultati osservati e delle risposte
  successive dell’atleta.

Matching, validazione, normalizzazione e valutazioni deterministiche sono il
fondamento di affidabilità dei dati su cui opera il coach. Non costituiscono,
da soli, l’intero motore di coaching e non devono ridurre IronCoach a un solo
sistema di confronto meccanico tra previsto e osservato.

## Significato di `INSUFFICIENT_DATA`

`INSUFFICIENT_DATA` descrive l’impossibilità di concludere **uno specifico
confronto quantitativo** con i dati disponibili. Non è uno stato globale del
coach e non deve bloccare automaticamente ogni feedback dell’IA.

Quando un confronto è insufficiente, IronCoach può comunque:

- riportare i fatti osservati disponibili;
- spiegare perché quel confronto non è conclusivo;
- offrire interpretazioni qualitative supportate dalla storia disponibile;
- porre domande facoltative e pertinenti per ridurre l’incertezza;
- proporre passi successivi, purché siano presentati con il corretto grado di
  cautela.

Non deve invece inventare, stimare tacitamente o convertire per supposizione
misure mancanti allo scopo di rendere il confronto valutabile.

## Contratto di comunicazione del coach

Ogni risposta prodotta dal coach deve rendere distinguibili:

1. **Dati osservati** — misure, eventi e dichiarazioni realmente disponibili,
   con sorgente e provenienza coerenti.
2. **Interpretazioni** — analisi o spiegazioni costruite a partire dai dati,
   senza presentarle come misure osservate.
3. **Incertezze** — dati mancanti, ambiguità, limiti del confronto e grado di
   confidenza delle conclusioni.

Questa separazione vale anche quando l’IA produce una risposta utile in
presenza di `INSUFFICIENT_DATA`. L’utilità del feedback non autorizza a
riempire i vuoti informativi né a promuovere segnali non qualificati a misure
canoniche.

## Vincolo di implementazione

Le future funzionalità di analisi, spiegazione, pianificazione per una gara e
revisione del piano devono rispettare questo principio e appoggiarsi ai
contratti deterministici esistenti come guardrail di affidabilità.

Questo requisito non autorizza scorciatoie o generatori di piani improvvisati:
ogni capacità di pianificazione basata sull’IA richiede un proprio contratto,
provenienza verificabile, gestione esplicita dell’incertezza e test dedicati.
Il lavoro circoscritto sulla raccolta dell’RPE osservato resta separato da tale
futura capacità di generazione dei piani.
