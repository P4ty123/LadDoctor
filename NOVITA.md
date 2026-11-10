## LagDoctor 5.7.6

- "Riduci i processi svchost": ora la soglia e' esattamente la RAM INSTALLATA in KB (32 GB = 2000000 esadecimale)
  invece della RAM utilizzabile (un po' meno, che poteva lasciare i servizi separati). La voce risulta attiva anche
  se il valore e' stato impostato a mano uguale o maggiore.

## LagDoctor 5.7.5

- Game mode: controlla se e' partito un gioco ogni 5 secondi invece di 2 (ancora meno lavoro in background).

## LagDoctor 5.7.4

- Aggiornamento: la finestra della versione vecchia ora si chiude da sola, invece di restare aperta accanto a
  quella nuova.

## LagDoctor 5.7.3

- Pallino verde sul pulsante "Aggiornamenti" quando c'e' una versione nuova (anche con LagDoctor gia' aperto:
  il controllo si ripete ogni 15 minuti).
- Prima versione da installare con il pulsante "Aggiorna ora".

## LagDoctor 5.7.2 - correzioni importanti per la versione installata

- **Corretto: LagDoctor si chiudeva da solo pochi secondi dopo l'avvio** (blocco su "Controllo impostazioni" e
  errore "Failed to fetch" negli aggiornamenti). Edge, avviato da un programma amministratore, si riavvia da solo e
  LagDoctor pensava che la finestra fosse stata chiusa. Ora si chiude solo quando chiudi davvero la finestra.
- Corretto: i comandi di PowerShell avviati dalla versione installata potevano caricare librerie sbagliate e
  bloccarsi (es. controlli delle schede di rete).
- Controllo delle impostazioni piu' veloce (6 alla volta) e mai bloccato: una voce che non risponde entro 25 secondi
  diventa "non verificabile" e le altre vanno avanti (elenco in C:\ProgramData\LagDoctor\avvio_lento.log).
- Primo avvio: l'interfaccia si apre appena letto l'hardware, il resto continua in background.

## LagDoctor 5.7.1

- Primo avvio della versione installata: LagDoctor trova da solo la cartella della versione precedente (quella con
  AVVIA.bat su Desktop, Download o Documenti) e ne copia i dati: le modifiche gia' applicate restano annullabili e
  i report non si perdono.

## LagDoctor 5.7.0 - prima versione installabile

- **Programma installabile**: LagDoctor-Setup.exe con icone nel menu Start e sul desktop, disinstallazione da
  "App installate" (chiede se annullare tutte le modifiche).
- **Aggiornamenti automatici**: pulsante "Aggiornamenti" e avviso quando c'e' una versione nuova. L'installatore
  scaricato viene controllato (impronta SHA-256) prima di essere avviato.
- **Impostazioni**: avvio di LagDoctor con Windows, anche ridotto a icona.
- **Dati in C:\ProgramData\LagDoctor**: backup, report e configurazione restano dopo aggiornamenti e reinstallazioni
  (copiati automaticamente dalla versione precedente avviata con AVVIA.bat).
- Avvio veloce: l'hardware viene letto solo al primo avvio, le impostazioni in background.
- Game mode: affinita' dei core decisa in base al processore, giochi con anti-cheat gestiti in modo sicuro.
- Supporto migliore per le grafiche integrate (Intel e AMD).
- La finestra si chiude insieme al programma; aprendo LagDoctor una seconda volta si riapre la finestra esistente.
