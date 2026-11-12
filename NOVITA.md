## LagDoctor 5.17.2

- Overlays: tolta dai dettagli la riga arancione "Attenzione: ...", che ripeteva "Possibili problemi".

## LagDoctor 5.17.1

- Overlays: sotto il nome di ogni voce resta solo "dettagli"; la descrizione breve e' stata spostata in cima ai dettagli.

## LagDoctor 5.17.0

- Overlays: ora si spengono anche da LagDoctor, con l'interruttore e Applica (ogni modifica si annulla):
  - Steam, app EA, Ubisoft Connect: LagDoctor chiude il programma e spegne l'overlay nelle sue impostazioni
    (prima di applicare ti dice quali programmi verranno chiusi).
  - NVIDIA, AMD Software, RivaTuner, Overwolf: LagDoctor chiude l'overlay, ne toglie l'avvio con Windows
    (RivaTuner, Overwolf) e la Game mode lo richiude a ogni partita se si e' riaperto.
  - Discord, Intel e GOG Galaxy non hanno un'impostazione modificabile dall'esterno: resta "Come spegnerlo".
- Overlay dell'app EA: lo stato ora viene letto dalle sue impostazioni.

## LagDoctor 5.16.0

- Ottimizzazioni: nuova categoria "Overlays".
  - In cima, "Overlay attivi adesso": i programmi che in questo momento si agganciano ai giochi (Steam, NVIDIA,
    AMD, RivaTuner, Overwolf, EA, Epic, Xbox Game Bar, Medal), con il pulsante Aggiorna.
  - Sotto, gli overlay dei programmi installati sul PC (Steam, NVIDIA App / GeForce Experience, AMD Software,
    Intel, Discord, RivaTuner / MSI Afterburner, Overwolf, EA, Ubisoft Connect, GOG Galaxy) con lo stato
    (acceso, spento, attivo ora, da controllare) e "Come spegnerlo": dove disattivarlo nel programma.
  - Spostate qui le voci di Windows che riguardano gli overlay: registrazione Xbox Game Bar, Game DVR di sistema,
    apertura della Game Bar con Win+G / tasto Xbox, MPO (Multiplane Overlay).
- Il pulsante Ignora ora sta accanto a "dettagli", cosi' i controlli a destra restano su una riga.

## LagDoctor 5.15.0

- Nuova pagina Ottimizzazioni: categorie a sinistra (con quante voci sono attive e un pallino rosso se c'e' qualcosa
  da correggere) e voci a destra.
- Accanto a ogni voce: i pallini dell'effetto (piu' pallini = piu' effetto) e il rischio colorato
  (Sicura verde, Moderata gialla, Rischiosa arancione, Pericolosa rossa), poi l'interruttore.
- Si accende l'interruttore delle voci che si vogliono e si preme Applica. Sulle voci applicate da LagDoctor
  l'interruttore annulla la modifica. Il pulsante Ignora compare passando col mouse sulla voce.

## LagDoctor 5.14.0

- Ottimizzazioni: pulsante "Ignora" su ogni voce e nuova sezione "Ignorate". Le voci ignorate non compaiono tra
  quelle da correggere o consigliate e non contano nel punteggio del PC; con "Non ignorare" tornano al loro posto.

## LagDoctor 5.13.4

- Il progetto su GitHub ora si chiama LagDoctor (prima LadDoctor): aggiornamenti e collegamenti usano il nome nuovo.
  Le versioni precedenti continuano a trovare gli aggiornamenti grazie al reindirizzamento di GitHub.

## LagDoctor 5.13.3

- Stato reale anche per SystemResponsiveness (10 o meno), nomi 8.3 (1 o 3), WaitToKillServiceTimeout (2000 o meno),
  ottimizzazioni schermo intero, Recall, app in background e Sensore memoria (anche con le altre chiavi di Windows).

## LagDoctor 5.13.2

- Le ottimizzazioni gia' attive grazie ad altri programmi (es. EXM) o impostate a mano ora vengono riconosciute:
  - Timer Resolution: conta il timer reale di Windows (~0,5 ms), chiunque lo tenga;
  - Effetti visivi: contano le caselle realmente spente, non chi le ha spente;
  - Esclusione di Defender: controlla se una cartella di giochi e' gia' esclusa;
  - accelerazione del mouse, scorciatoie di accessibilita', "ultimo accesso" NTFS, Game DVR, Modalita' Gioco,
    widget, Copilot, ricerca Bing, Ottimizzazione recapito, telemetria, ritardo dei menu, IPv4: contano anche i
    valori equivalenti impostati dalle Impostazioni di Windows o da altri programmi.
  Queste voci non compaiono piu' tra quelle da applicare se sono gia' attive.

## LagDoctor 5.13.0

- Nuove voci consigliate (applicabili tutte insieme con "Seleziona consigliate"): telemetria e pubblicita' al
  minimo, effetti visivi, Timer Resolution 0,5 ms, widget spenti, Edge non in background, Recall spento, ricerca
  del menu Start senza Bing, niente "ultimo accesso" NTFS, scorciatoie Tasti permanenti / Filtro tasti spente,
  programmi di avvio senza attesa, menu istantanei.
- "GlobalTimerResolutionRequests" e "Timer Resolution 0,5 ms" sono ora un'unica voce (servono insieme).

## LagDoctor 5.12.0

- Effetti visivi rifatti: come la finestra "Opzioni prestazioni" di Windows spegne tutte le caselle (animazioni,
  ombre, dissolvenze, scorrimento fluido, trascinamento, trasparenze, Peek) lasciando attivi "Smussa gli angoli dei
  caratteri" e "Mostra anteprime anziche' icone". Effetto immediato; Annulla rimette ogni casella com'era.
- Nuova ottimizzazione: spegnimento piu' rapido (WaitToKillServiceTimeout = 2000).

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
