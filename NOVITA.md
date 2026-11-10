## LagDoctor 5.11.1

- Spegnendo la game mode il messaggio dice cosa e' stato annullato davvero: "Game mode spenta" se non c'era niente
  da annullare, "ottimizzazioni del gioco annullate" solo se un gioco era aperto.

## LagDoctor 5.11.0

- Game mode: priorita' bassa anche per disco e memoria dei programmi in background. Quando il gioco carica dati dal
  disco passa per primo, e la sua memoria viene liberata per ultima.
- Game mode: priorita' bassa per i programmi dei produttori di PC (Dell SupportAssist, HP Touchpoint/Analytics,
  Lenovo Vantage, servizi ASUS e MSI). Restano accesi, lavorano solo quando il gioco non ne ha bisogno.
- Verifica: per ogni programma mostra anche disco e memoria; i programmi dei produttori hanno un gruppo a parte.

## LagDoctor 5.10.2

- Game mode: corretto il gioco che per qualche secondo all'avvio veniva messo a priorita' bassa insieme ai programmi
  in background (prima che la game mode gli desse la priorita' Alta).
- Tolto PcaSvc dai servizi da fermare: Windows lo riavvia a ogni programma che si apre.
- Verifica: i browser (Edge, Chrome...) che cambiano da soli la priorita' delle schede sono segnati come "da sapere".

## LagDoctor 5.10.1

- Game mode: i servizi di Windows Update (wuauserv, UsoSvc) che Windows fa ripartire da solo vengono fermati di
  nuovo mentre giochi.
- Priorita' GPU del gioco: ora si legge correttamente (permesso giusto) e la game mode attiva il privilegio di
  Windows necessario ad alzare le priorita'.
- La verifica e' ora un pannello a parte ("Verifica ottimizzazioni", disponibile appena la game mode si attiva, anche
  dalla Panoramica) che si aggiorna da solo, con l'elenco completo: ogni app chiusa e ogni programma messo a
  priorita' bassa, per nome.

## LagDoctor 5.10.0

- Game mode: nuova sezione "Verifica dal vivo". Mentre giochi controlla lo stato REALE di Windows per ogni
  ottimizzazione (priorita' CPU e GPU del gioco, affinita', servizi fermati, app chiuse, programmi in background,
  timer, rete QoS, piano energetico, RAM) e mostra ok / non applicata / da sapere, con il dettaglio.

## LagDoctor 5.9.3

- Utilizzo CPU piu' stabile nella Panoramica: media degli ultimi secondi come in Gestione attivita' (i picchi brevi,
  ad esempio all'apertura di un programma, non fanno piu' saltare il numero).

## LagDoctor 5.9.2

- Corretto l'utilizzo della CPU che restava sempre a 0: ora viene letto come in Gestione attivita'.
- Tolto il riquadro della temperatura della CPU.

## LagDoctor 5.9.1

- Panoramica: al posto di memoria video e frequenza della scheda video ci sono utilizzo CPU, temperatura CPU e
  utilizzo RAM (restano utilizzo e temperatura della GPU).
- Temperatura CPU: Windows non la fornisce direttamente. LagDoctor la legge da LibreHardwareMonitor se e' aperto
  (preciso), altrimenti dal sensore ACPI della scheda madre (indicativo; se e' un valore fisso non viene mostrato).

## LagDoctor 5.9.0

- Icona di LagDoctor vicino all'orologio (in basso a destra). Chiudendo la finestra con la X il programma resta
  acceso li': clic sull'icona per riaprirlo, tasto destro > Esci per chiuderlo davvero.
- Avvio con Windows "ridotto a icona": parte solo come icona, senza aprire la finestra.
- Aprendo LagDoctor quando e' gia' acceso, la sua finestra torna in primo piano (niente finestre doppie).

## LagDoctor 5.8.2

- Aggiornamenti: al posto dell'elenco di messaggi ripetuti c'e' una barra che si riempie, con la percentuale accanto.

## LagDoctor 5.8.1

- Corrette le linee chiare che lampeggiavano su alcuni riquadri (es. game mode e memoria video): erano causate
  dall'effetto "vetro" sfocato insieme allo sfondo sfumato fisso. L'aspetto resta lo stesso.

## LagDoctor 5.8.0 - nuova grafica

- Nuovo stile "gaming neon": sfondo scuro con riflessi viola e azzurri, riquadri in vetro, pulsanti con sfumatura,
  carattere Inter incluso nel programma (stesso aspetto anche senza internet).
- Panoramica rinnovata: punteggio del PC (indicativo, da 0 a 100: scende per ogni impostazione da correggere e per
  ogni problema del controllo rapido), riquadro della game mode con quello che sta facendo, sensori della scheda
  video con barre, avvisi di throttling, controllo rapido compatto con "Perche' e come risolvere".
- Tutte le pagine adottano il nuovo stile.

## LagDoctor 5.7.7

- Aggiornamento: la finestra della versione vecchia ora viene chiusa PRIMA di avviare l'installatore (prima
  l'installatore chiudeva il programma troppo presto e la finestra restava aperta).
- Il pulsante "Esci" chiude anche la finestra.

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
