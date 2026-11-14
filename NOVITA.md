## LagDoctor 5.25.8

- "Disattiva risparmio energetico della scheda di rete": non funzionava ("comando non riuscito"). Il comando usato
  spegneva solo Wake-on-LAN e simili, non "Consenti al computer di spegnere il dispositivo" di Gestione
  dispositivi. Ora LagDoctor la toglie come si fa a mano (PnPCapabilities della scheda) e la voce vale dopo il
  riavvio. Annulla rimette tutto com'era.
- Finestra dopo Applica: non dice piu' "Fatto" se qualcosa non e' andato. Il titolo dice quante modifiche sono
  riuscite e quante no, e le voci non riuscite sono in rosso in cima con il motivo. Ogni voce viene ricontrollata
  su Windows subito dopo l'applicazione: se Windows non la mostra attiva risulta NON riuscita (✘), se serve il
  riavvio lo dice (⟳).

## LagDoctor 5.25.7

- Game mode con "Chiudi Esplora risorse": a fine partita Esplora risorse torna entro 1-2 secondi (LagDoctor controlla
  ogni secondo se il gioco e' ancora aperto e lo riapre prima di tutto il resto).
- Tolto il rettangolo nero in basso a sinistra: erano le finestre ridotte a icona mentre mancava la barra delle
  applicazioni. Ora durante il gioco restano invisibili e alla fine tornano sulla barra delle applicazioni.
- Piani energetici: c'e' una sola voce, "Piano energetico 'Prestazioni eccellenti'" (Ultimate Performance). Se sul
  PC non c'e', LagDoctor lo crea da solo (powercfg -duplicatescheme). Tolte "Prestazioni elevate" e
  "Prestazioni migliori" (restano annullabili se applicate prima).
- Core parking, boost aggressivo, stato minimo CPU e le altre impostazioni energetiche applicate da LagDoctor ora
  vengono portate anche nel nuovo piano quando si attiva "Prestazioni eccellenti" e quando la game mode cambia
  piano durante il gioco (prima restavano solo nel piano di prima e in gioco non avevano effetto).
- Game mode, opzione del piano energetico: ora usa "Prestazioni eccellenti" invece di "Prestazioni elevate".

## LagDoctor 5.25.6

- Game mode con "Chiudi Esplora risorse": a fine partita Esplora risorse viene riaperto PER PRIMO (prima veniva
  riaperto dopo aver fatto ripartire servizi e attivita', e lo schermo restava grigio a lungo). Il resto viene
  ripristinato dopo, mentre usi gia' il PC.
- Viene chiuso solo Esplora risorse: Start, ricerca e shell restano (Windows le tiene gia' sospese). Alla fine la
  barra delle applicazioni si ridisegna piu' in fretta (era la causa probabile del rettangolo nero in basso a sinistra).

## LagDoctor 5.25.5

- Finestra senza barra di Edge: trovata e corretta la causa del blocco ("non risponde" pochi secondi dopo
  l'apertura). Un controllo di LagDoctor leggeva WebView2 dal thread sbagliato e la finestra e LagDoctor si
  aspettavano a vicenda. Il blocco e' stato riprodotto e la correzione provata su un PC Windows vero: apertura,
  nessun blocco, nessuna schermata nera, trascinamento, ridimensionamento da tutti i bordi e dall'angolo,
  ingrandisci / ripristina (tasto e doppio clic sulla barra).
- La finestra nuova torna accesa di base (si puo' spegnere in Impostazioni). Se su un PC desse ancora problemi,
  LagDoctor riprova con la grafica software e poi torna da solo alla finestra di Edge.
- Se la finestra si blocca, il registro (errore-finestra.txt) ora indica il punto esatto del blocco.

## LagDoctor 5.25.4

- La finestra torna quella di Edge (stabile). La finestra senza barra di Edge diventa sperimentale: si accende da
  Impostazioni > "Finestra senza barra di Edge (sperimentale)" e vale dalla prossima apertura.
- Con la finestra sperimentale accesa: se va in errore, alla prossima apertura LagDoctor riprova con la grafica
  in modalita' software; se va in errore anche cosi', torna da solo alla finestra di Edge (riaccendendo
  l'interruttore si riprova da capo).
- Registro piu' completo per capire il problema: ogni fase dell'apertura e gli errori di .NET in
  errore-finestra.txt, i messaggi di .NET e di WebView2 in finestra-console.txt (cartella dei dati).

## LagDoctor 5.25.3

- Finestra nuova: dopo pochi secondi poteva diventare tutta nera.
  - Tolta l'ombra della finestra senza bordo (un effetto di Windows che con WebView2 puo' dare schermate nere).
  - Se il motore di WebView2 chiude il processo che disegna la pagina, LagDoctor la ricarica da solo; se succede
    piu' volte, apre la finestra di Edge come prima.
  - Se la finestra e' in primo piano ma la pagina non risponde da 45 secondi, LagDoctor apre la finestra di Edge.
  - Ogni problema viene scritto con il motivo in errore-finestra.txt.

## LagDoctor 5.25.2

- Finestra nuova: trovata la causa del caricamento infinito, del "non risponde" e della chiusura (5.25.0 e
  5.25.1). Al caricamento della pagina WebView2 esplorava anche la finestra stessa e aspettava fino a 15 secondi
  per ognuna delle sue misure, bloccandosi. Ora non succede piu'.
- Protezione in piu': se la finestra nuova non risponde per 20 secondi, LagDoctor la chiude e apre quella di Edge
  come prima.

## LagDoctor 5.25.1

- Finestra nuova (senza barra di Edge): nella 5.25.0 si chiudeva pochi secondi dopo averla cliccata. Ora usa solo
  le funzioni ufficiali di WebView2/pywebview per trascinare, ingrandire e ridimensionare (non piu' comandi diretti
  di Windows sulla finestra).
- Se la finestra nuova si chiude con un errore, in qualsiasi momento, LagDoctor apre subito la finestra di Edge
  come prima e con questa versione non riprova. Il motivo viene scritto in errore-finestra.txt nella cartella dei
  dati di LagDoctor.

## LagDoctor 5.25.0

- Finestra nuova, senza la barra grigia di Edge in alto: la barra del titolo e' quella di LagDoctor, nello stesso
  stile del programma, con riduci a icona, ingrandisci e chiudi (rosso quando ci passi sopra). La finestra si
  trascina dalla barra in alto o dal logo e si ridimensiona dai bordi; funzionano anche Snap (trascinala in alto
  o ai lati dello schermo) e Win+frecce. Chiudendola LagDoctor resta vicino all'orologio, come prima.
- La finestra ora usa WebView2 (lo stesso motore di Edge, dentro il programma). Se su un PC WebView2 non funziona,
  LagDoctor apre da solo la finestra di Edge come prima.

## LagDoctor 5.24.2

- Animazioni: in Driver video e Ottimizzazioni prima compariva un breve "Leggo le impostazioni..." e la pagina
  vera appariva di colpo, senza animazione. Ora l'animazione parte sul contenuto vero; il caricamento resta
  nascosto se dura poco e compare in dissolvenza solo se dura di piu'.
- Nuova icona con il logo nuovo: barra del titolo della finestra, LagDoctor.exe, installazione, collegamenti e
  icona vicino all'orologio.

## LagDoctor 5.24.1

- Animazioni al cambio di scheda: non comparivano sui PC con gli "Effetti di animazione" di Windows spenti
  (spesso li spengono le ottimizzazioni degli effetti visivi). Ora decide solo l'interruttore Impostazioni >
  Animazioni.

## LagDoctor 5.24.0

- Animazioni al cambio di scheda: la pagina vecchia scompare e la nuova entra dal basso, sia per le schede del
  menu sia per le sotto-schede (Analizza gioco, Avvio automatico, categorie e filtri di Ottimizzazioni).
  Si possono spegnere da Impostazioni > Animazioni (di base sono accese). Restano spente se in Windows sono
  disattivati gli effetti di animazione.
- Analizza gioco > Sessioni: si possono eliminare le sessioni registrate, una alla volta (cestino sulla riga) o
  piu' insieme (Seleziona tutte / Elimina selezionate), sempre con una conferma. Vengono cancellati anche il
  report e i dati registrati della sessione. La partita PRIMA di un test Prima / Dopo in corso non viene eliminata.

## LagDoctor 5.23.0

Interfaccia rinnovata:
- Nuovo logo. Sotto il nome ora c'e' solo il numero di versione.
- Nuovo stile dei pulsanti (icona in un riquadro colorato, freccia che scorre) per "Scansione completa", per
  Analizza gioco e per i pulsanti in basso a sinistra (Impostazioni, Aggiornamenti, Cartella report, Ripristina
  tutto, Esci), ognuno con la sua icona.
- Panoramica: tolti i due pulsanti "Analizza un gioco" e la riga "Monitor". "Scansione completa" e' nel
  riquadro del punteggio. Nel riquadro della Game mode una freccia porta direttamente alla sua sezione.
- Menu: tolta la voce "Scansione". La scansione completa si apre dalla Panoramica.
- Analizza gioco rifatta: i passaggi in alto, i giochi aperti come schede da scegliere, la durata con pulsanti e
  un riepilogo prima di avviare. Registrazione in corso, risultato (con il giudizio Fluido / Qualche scatto /
  Molti scatti), Sessioni e Prima / Dopo nello stesso stile.
- Tolte le voci "Non affidabili" (tweak famosi che non funzionano o peggiorano). Se LagDoctor ne aveva attivata
  qualcuna in passato, "Ripristina tutto" la annulla ancora.

## LagDoctor 5.22.2

- CPU ed energia, controllate tutte le voci:
  - Core parking, stato minimo del processore, boost, idle, sospensione USB e ASPM sono impostazioni che stanno
    DENTRO un piano energetico. Prima, se dopo averle applicate si cambiava piano (es. 'Prestazioni elevate'),
    smettevano di funzionare, e "Annulla" scriveva i vecchi valori nel piano sbagliato. Ora vengono riportate
    anche nel nuovo piano e "Annulla" rimette ogni piano com'era.
  - CPU Intel ibride (12a generazione e successive): "Disattiva core parking" e "Stato minimo processore al
    100%" agivano solo su una classe di core. Ora valgono anche per i P-core.
  - "Prestazioni elevate": su molti portatili e PC con Modern Standby Windows nasconde questo piano e la voce
    dava errore. Ora LagDoctor lo ricrea (come fa gia' per 'Prestazioni ottimali') e lo riconosce per nome.
  - Gli errori di powercfg ora vengono segnalati invece di risultare "applicata".

## LagDoctor 5.22.1

- Esclusioni di Defender, ricerca dei giochi sui dischi piu' precisa (niente programmi scambiati per giochi):
  - Launcher e client non sono piu' proposti come giochi: Epic Games Launcher, GOG Galaxy, REDlauncher di
    CD Projekt, Minecraft Launcher, Battle.net, EA, Riot Client, Ubisoft Connect.
  - Strumenti e mod non sono piu' proposti: OptiScaler, ReShade, Special K, emulatori di Steam/Epic/GOG
    (Goldberg, Nemirtingas), bypass, trainer e gli strumenti di Nucleus Co-op.
  - Le DLL di DLSS / FSR / XeSS non bastano piu' per dire che una cartella e' un gioco (le hanno anche le mod).
    Una DLL di Steam, Epic, GOG, Bink, FMOD, PhysX o di un anti-cheat conta solo se nella cartella ci sono anche
    un .exe e i dati di un gioco (archivi .pak, .arc, .bundle... o cartelle come Data, Content, Paks).
  - La cartella di un client (es. GOG Galaxy) non viene piu' proposta come "raccolta di giochi".

## LagDoctor 5.22.0

- "Escludi le cartelle dei giochi da Defender" (prima "...la cartella..."):
  - Prima veniva proposta una sola cartella, presa dall'ultimo gioco analizzato (spesso un singolo gioco).
    Ora la finestra mostra TUTTE le cartelle dei giochi su TUTTI i dischi, ognuna con la sua spunta, il disco,
    quanti giochi contiene e da dove arriva. Si puo' aggiungere anche una cartella a mano.
  - Le cartelle arrivano dai launcher (Steam con tutte le sue librerie, Epic, GOG, Xbox, Ubisoft, EA, Riot,
    Rockstar...) e da una ricerca su tutti i dischi fissi per i giochi senza launcher: un gioco viene
    riconosciuto dai file tipici dei motori e degli SDK per giochi (Unity, Unreal, Steamworks, Epic Online
    Services...). La ricerca non entra nelle cartelle di sistema e dura al massimo una dozzina di secondi.
  - Viene proposta la cartella che raccoglie i giochi (es. ...\steamapps\common, D:\Giochi, F:\XboxGames).
    Un gioco da solo in una cartella qualsiasi (es. Download) viene proposto da solo, per non escludere tutta
    quella cartella.
  - La voce risulta attiva solo se TUTTI i giochi trovati sono esclusi. Se ne mancano (es. giochi installati
    dopo o su un nuovo disco), compare il pulsante "Aggiungi cartelle".
  - Se una cartella non si riesce a escludere, quelle gia' aggiunte vengono tolte: tutto torna come prima.

## LagDoctor 5.21.5

- "Escludi la cartella dei giochi da Defender":
  - Non esclude piu' cartelle troppo ampie: un disco intero (es. C:\), Windows, Programmi, ProgramData, Utenti,
    il profilo utente e AppData. Prima la cartella proposta era quella sopra l'ultimo gioco analizzato e, con un
    gioco in C:\Gioco o in C:\Programmi\Gioco, poteva essere l'intero disco C: o tutta la cartella Programmi.
  - Se la cartella era gia' esclusa prima (da te o da un altro programma), "Annulla" non la toglie piu'.
  - Se Defender rifiuta di togliere l'esclusione, ora viene segnalato invece di risultare "annullata".
  - Lettura dello stato: la risposta di Defender "N/A: serve l'amministratore" non viene piu' scambiata per una
    cartella, e le esclusioni scritte con variabili (es. %USERPROFILE%\Giochi) vengono riconosciute.

## LagDoctor 5.21.4

- "Preferisci IPv4 a IPv6": il valore di Windows usato (DisabledComponents) contiene piu' impostazioni IPv6
  insieme. Prima LagDoctor lo sovrascriveva con 0x20 e cancellava le altre (es. tunnel IPv6 spenti, che si
  riaccendevano). Ora aggiunge solo "preferisci IPv4" e lascia il resto com'era; "Annulla" rimette il valore
  esatto di prima.

## LagDoctor 5.21.3

- AMD Software Adrenalin: controllate tutte le chiamate ADLX con gli header ufficiali AMD. Corretti tre errori:
  - "Radeon Super Resolution" e "AMD Fluid Motion Frames" venivano chiesti passando anche la scheda video, ma
    queste due funzioni non la vogliono: il driver scriveva il risultato dentro i dati della scheda (memoria
    corrotta, possibili chiusure improvvise) e le due voci risultavano sempre "non supportate".
  - AMD Fluid Motion Frames e il livello di Anti-Lag esistono solo nei driver recenti: ora vengono chiesti nel
    modo previsto da AMD (QueryInterface). Prima, con un driver vecchio, LagDoctor poteva chiudersi.

## LagDoctor 5.21.2

- Pannello di controllo NVIDIA: corretta la struttura usata per leggere e scrivere le impostazioni del driver
  (era spostata di 4 byte rispetto a quella ufficiale NVAPI). Le voci del driver NVIDIA potevano risultare non
  attive anche se impostate nel Pannello (es. "Gestione energia: Prediligi prestazioni massime" letta come
  "Adattiva"). Inoltre, quando le applicava LagDoctor, il valore veniva scritto in modo sbagliato nel driver.

## LagDoctor 5.21.1

Collaudo automatico di tutte le voci (applica -> risulta attiva -> annulla -> tutto come prima) su un Windows
simulato: 108 voci di Windows e 25 dei driver NVIDIA/AMD. Correzioni trovate:
- "Telemetria e pubblicita' al minimo": applicata da LagDoctor risultava non attiva (l'impostazione veniva scritta
  in una posizione del registro e controllata in un'altra). Ora controlla entrambe.
- Windows in italiano: i comandi che scrivono lettere accentate (bcdedit "Si'", powercfg...) potevano non essere
  letti e la voce risultava "?". Ora l'output dei comandi viene letto con la codifica giusta.
- "Disattiva dynamic tick", "Disattiva l'hypervisor" e "Forza HPET": riconoscono il "Si'" di bcdedit in italiano.
- Verifica completa: per le voci "?" mostra il motivo vero (es. "Prestazioni migliori": serve il piano Bilanciato).

## LagDoctor 5.21.0

- Nuova "Verifica completa" (Impostazioni > Verifica completa > Apri): controlla una per una tutte le ottimizzazioni,
  la game mode e le altre funzioni (avvio con Windows, guardiano degli overlay, programmi e processi disattivati)
  e per ognuna dice se su questo PC funziona davvero: ✔ funziona, ✘ problema (applicata ma non attiva),
  ⟳ serve il riavvio, ○ non attiva, ? non leggibile. Mostra cosa ha letto su Windows, ha "solo problemi",
  "Copia risultati" e salva un file nella Cartella report. Solo lettura.

## LagDoctor 5.20.5

- Game mode, "Chiudi Esplora risorse": Windows lo riapriva da solo dopo pochi secondi. Ora durante il gioco viene
  sospeso il riavvio automatico di Esplora risorse (AutoRestartShell) e alla fine della partita tutto viene rimesso
  com'era e Esplora risorse riaperto, anche dopo un crash o uno spegnimento.

## LagDoctor 5.20.4

- Icona vicino all'orologio: sui PC lenti o appena accesi (es. mini PC) l'area di notifica puo' rispondere in
  ritardo e l'icona non veniva creata, quindi chiudendo la finestra LagDoctor si chiudeva del tutto. Ora riprova
  per circa 30 secondi e, se l'icona compare dopo, chiudere la finestra la riduce comunque a icona.

## LagDoctor 5.20.3

- Timer Resolution: la voce risulta attiva solo se il timer e' davvero a 0,5 ms (prima bastava che esistesse
  l'attivita' all'avvio, anche se il processo si era chiuso con un errore).

## LagDoctor 5.20.2

- Corretto l'errore "partially initialized module lagdoctor.extra_tweaks" all'accesso a Windows: il processo
  invisibile del Timer Resolution (LagDoctor.exe --timer) si chiudeva subito con questa finestra di errore,
  quindi il timer a 0,5 ms all'avvio non funzionava.

## LagDoctor 5.20.1

- Avvio automatico > Processi in background: corretta la lettura (prima risultava vuota). I servizi ora vengono
  letti direttamente da Windows senza PowerShell; le attivita' pianificate con uno script su file. Spegnere e
  riattivare usa sc e schtasks. Se una delle due letture non riesce, l'altra viene mostrata lo stesso con il motivo.

## LagDoctor 5.20.0

- Avvio automatico, nuova scheda "Processi in background": servizi e attivita' pianificate che partono con Windows
  e che Gestione attivita' non mostra, divisi in aggiornamenti automatici, programmi del produttore, giochi e
  launcher, driver e hardware, altri programmi. Per ognuno: da dove parte, se e' in esecuzione e quanta RAM usa.
  - Spegnendo l'interruttore LagDoctor toglie l'avvio alla fonte (servizio Disattivato, attivita' disattivata) e lo
    ferma una volta: non si riapre, niente chiusure continue. Riaccendendolo (o con Ripristina tutto) torna com'era.
  - Driver, antivirus e anti-cheat hanno l'interruttore bloccato; i componenti di Windows sono nascosti (si possono
    vedere, in sola lettura, con "Mostra anche i componenti di Windows").
- Scheda "Programmi": righe piu' compatte con stato (in esecuzione / fermo) e RAM usata.

## LagDoctor 5.19.2

- Game mode, elenco dei giochi: righe piu' basse e senza il percorso della cartella sotto ogni gioco.

## LagDoctor 5.19.1

- Game mode, "Cosa fa durante il gioco": ogni voce mostra solo il nome; spiegazione, possibili problemi e cosa ha
  deciso LagDoctor per il tuo PC si aprono con il pulsante "dettagli".

## LagDoctor 5.19.0

- Game mode, nuove opzioni:
  - "Manutenzione di Windows in pausa" (accesa): durante il gioco vengono sospese le attivita' pianificate che
    partono a orari casuali (telemetria CompatTelRunner, scansioni pianificate e manutenzione di Defender,
    ottimizzazione dischi, diagnostica, aggiornamenti di Office) e la Manutenzione automatica. Se una era gia'
    partita viene chiusa una volta: non si riapre perche' le attivita' restano sospese. Tutto riparte a fine partita.
  - "Modalita' efficienza per i programmi in background" (accesa, decide LagDoctor): usata solo dove rende di piu'
    della priorita' bassa (processori con core di due tipi e portatili); sugli altri resta la priorita' bassa.
  - "Svuota la memoria in standby quando la RAM libera sta finendo" (facoltativa): solo sotto 1 GB liberi.
  - "Scheda video ad alte prestazioni per i giochi" (facoltativa): solo sui PC con due schede video.
- Verifica dal vivo della game mode: righe per le nuove opzioni.

## LagDoctor 5.18.1

- Overlays, interruttore: acceso = overlay spento (come le altre ottimizzazioni), chiunque l'abbia spento
  (LagDoctor o tu dal suo programma). Overlay acceso = interruttore spento, sempre libero: lo accendi e premi
  Applica per spegnere l'overlay. Su un overlay spento da LagDoctor, spegnere l'interruttore lo riaccende.
- Se riaccendi tu un overlay dal suo programma (Steam, app EA, Ubisoft Connect), LagDoctor non lo rispegne:
  l'interruttore torna spento e libero, come se non fosse mai stato toccato, e puoi rispegnerlo da qui.

## LagDoctor 5.18.0

- Overlays: un overlay spento da LagDoctor ora RESTA spento, anche dopo il riavvio del PC. Un piccolo processo
  invisibile (attivita' "LagDoctor Overlay", parte all'accesso solo se c'e' almeno un overlay spento da LagDoctor):
  - richiude entro pochi secondi gli overlay che si riaprono (NVIDIA, AMD, RivaTuner, Overwolf);
  - rimette l'impostazione se Steam, l'app EA o Ubisoft Connect la riaccendono (appena il programma viene chiuso).
  Riaccendendo l'interruttore l'overlay torna come prima; quando non resta nessun overlay spento il processo si ferma.
- Overlay spento dal suo programma (non da LagDoctor): l'interruttore non e' piu' bloccato. Se l'overlay si
  riaccende, l'interruttore torna acceso e si puo' spegnere da LagDoctor.
- Nuovo stato "spento da LagDoctor".

## LagDoctor 5.17.3

- Overlays: l'interruttore ora mostra l'overlay stesso. Acceso = overlay acceso; per spegnerlo spegni l'interruttore
  e premi Applica. Su un overlay spento da LagDoctor, riaccendere l'interruttore lo rimette come prima.
- Se un overlay spento da LagDoctor si riapre (es. NVIDIA dopo il riavvio), l'interruttore torna acceso e si puo'
  spegnere di nuovo.
- In cima alla categoria: quanti overlay sono accesi, spenti e da controllare.
- Overlay AMD: se il suo processo non e' aperto risulta spento.

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
