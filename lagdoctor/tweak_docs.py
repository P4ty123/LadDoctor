"""Spiegazioni dettagliate di ogni voce del catalogo.

Per ogni voce:
  cosa     = a cosa serve l'impostazione di Windows (com'e' di default)
  perche   = perche' cambiarla puo' aiutare
  problemi = cosa puo' andare storto cambiandola ("Nessuno" se non ci sono controindicazioni note)
"""

D = {}


def doc(tid, cosa, perche, problemi):
    D[tid] = {"cosa": cosa, "perche": perche, "problemi": problemi}


# ------------------------------------------------------------------ CORREZIONI
doc("fix_hpet",
    "useplatformclock obbliga Windows a usare il vecchio timer HPET della scheda madre come orologio di sistema.",
    "Leggere l'HPET e' molto piu' lento del timer moderno della CPU: con useplatformclock attivo aumentano latenza e "
    "stutter. Toglierlo riporta Windows al comportamento normale.",
    "Nessuno: e' l'impostazione predefinita di Windows.")
doc("fix_pagefile",
    "Il file di paging e' lo spazio su disco che Windows usa come 'RAM di riserva' quando quella vera si riempie.",
    "Senza file di paging, quando la RAM finisce i giochi vanno in crash o si bloccano invece di rallentare un "
    "attimo. Molti giochi moderni lo richiedono anche con 32 GB.",
    "Usa qualche GB di spazio su disco. Nessun effetto negativo sulle prestazioni.")
doc("fix_autotuning",
    "L'auto-tuning TCP adatta la quantita' di dati che il PC puo' ricevere alla velocita' della tua connessione.",
    "Disattivarlo (vecchio 'tweak di rete') limita la velocita' di download di giochi e aggiornamenti senza "
    "abbassare il ping. Riattivarlo riporta la velocita' piena.",
    "Nessuno: e' l'impostazione predefinita di Windows.")
doc("fix_largecache",
    "LargeSystemCache decide quanta RAM Windows riserva alla cache dei file di sistema.",
    "Con valore 1 (modalita' server) Windows toglie RAM ai programmi per la cache: ai giochi ne resta meno.",
    "Nessuno: 0 e' il valore predefinito per i PC desktop.")
doc("fix_clearpagefile",
    "ClearPageFileAtShutdown cancella il contenuto del file di paging a ogni spegnimento (per sicurezza dei dati).",
    "Rende lo spegnimento molto piu' lento e non migliora nulla nei giochi: e' un residuo di vecchie guide.",
    "Nessuno per un PC di casa (serve solo in ambienti con dati molto riservati).")
doc("fix_powersaver",
    "Il piano 'Risparmio energia' limita frequenza della CPU e consumi per allungare la batteria.",
    "Su un PC da gioco toglie prestazioni: la CPU non sale alle frequenze massime.",
    "Qualche watt di consumo in piu' (trascurabile su un desktop).")
doc("fix_hags_off_40",
    "HAGS (pianificazione GPU con accelerazione hardware) fa gestire alla scheda video la coda dei frame invece che "
    "alla CPU.",
    "Sulle RTX 40/50 e' necessario per DLSS Frame Generation e in genere riduce leggermente la latenza.",
    "In rari giochi o con driver vecchi puo' causare stutter: se succede, annulla la modifica.")
for _id, _name, _why in [
        ("wuauserv", "Windows Update", "senza di esso non arrivano aggiornamenti di sicurezza, driver e componenti DirectX; "
                                       "anche Xbox App e Game Pass smettono di aggiornare i giochi"),
        ("bits", "BITS", "serve a scaricare in background aggiornamenti di Windows, Xbox App, Epic e altri launcher"),
        ("audiosrv", "Audio di Windows", "senza di esso il PC non ha audio"),
        ("audioendpointbuilder", "Generatore endpoint audio", "gestisce cuffie e casse: senza, l'audio non funziona"),
        ("gamingservices", "Gaming Services", "serve per installare e avviare i giochi Xbox / Game Pass"),
        ("xblauthmanager", "Xbox Live Auth Manager", "serve per l'accesso all'account Xbox nei giochi"),
        ("dnscache", "Client DNS", "ricorda gli indirizzi dei siti: senza, ogni connessione e' piu' lenta"),
        ("mpssvc", "Windows Firewall", "protegge il PC dalla rete; alcuni giochi e anti-cheat non partono senza"),
        ("schedule", "Utilita' di pianificazione", "esegue le attivita' programmate di Windows, driver e launcher"),
        ("themes", "Temi", "gestisce l'aspetto di Windows; disattivarlo non da' benefici nei giochi")]:
    doc("fix_svc_" + _id, "Servizio di sistema '%s': %s." % (_name, _why),
        "E' stato DISATTIVATO, probabilmente da uno script 'debloat' o da un ottimizzatore: riattivarlo sistema i "
        "problemi senza costare prestazioni (un servizio inattivo non usa CPU).",
        "Nessuno: e' l'impostazione predefinita di Windows.")
doc("fix_trim",
    "Il TRIM dice all'SSD quali dati sono stati cancellati, cosi' puo' riorganizzarsi in background.",
    "Senza TRIM l'SSD rallenta col tempo (caricamenti e streaming dei giochi piu' lenti) e si consuma di piu'.",
    "Nessuno: e' l'impostazione predefinita di Windows.")

# ------------------------------------------------------------------ GIOCO
doc("game_dvr",
    "Game DVR (Xbox Game Bar) registra continuamente gli ultimi secondi di gioco per poterli salvare come clip.",
    "La registrazione continua usa GPU (codifica video) e disco mentre giochi: e' una causa nota di micro-scatti.",
    "Non potrai piu' salvare le clip 'registra quello che e' appena successo' con Win+Alt+G. Gli screenshot "
    "funzionano ancora.")
doc("game_mode",
    "La Modalita' Gioco fa dare a Windows la priorita' al gioco e rimanda aggiornamenti e notifiche.",
    "Riduce le attivita' in background mentre giochi (soprattutto aggiornamenti e driver che si installano da soli).",
    "Nessuno noto con Windows 11 aggiornato.")
doc("windowed_opt",
    "Impostazione di Windows 11 che fa usare ai giochi DirectX 10/11 in finestra o borderless il sistema di "
    "presentazione moderno ('flip model').",
    "Meno latenza in borderless, frame pacing migliore e possibilita' di usare VRR e Auto HDR (Microsoft).",
    "Qualche gioco molto vecchio potrebbe avere problemi grafici: puoi escluderlo da Impostazioni > Schermo > "
    "Grafica.")
doc("vrr_opt",
    "Impostazione 'Frequenza di aggiornamento variabile' di Windows (Impostazioni > Schermo > Grafica).",
    "Permette a G-SYNC/FreeSync di funzionare anche nei giochi DirectX 11 che non lo supportano da soli: meno "
    "tearing e scatti quando gli FPS scendono sotto la frequenza del monitor.",
    "Serve un monitor G-SYNC/FreeSync. In rari casi lo schermo puo' sfarfallare nei menu: se succede, annulla.")
doc("hags",
    "HAGS (pianificazione GPU con accelerazione hardware) fa gestire alla scheda video la coda dei frame.",
    "Riduce leggermente latenza e uso CPU; obbligatorio per DLSS Frame Generation sulle RTX 40/50.",
    "Su schede o driver vecchi puo' causare stutter o problemi con alcuni programmi di registrazione. Si prova "
    "con il test prima/dopo.")
doc("fso_off",
    "Le 'ottimizzazioni schermo intero' trasformano lo schermo intero esclusivo in una finestra speciale gestita "
    "da Windows (per Alt+Tab veloce e overlay).",
    "In alcuni giochi vecchi lo schermo intero esclusivo vero ha latenza un po' piu' bassa.",
    "Alt+Tab piu' lento (lo schermo diventa nero un attimo), Auto HDR e alcuni overlay possono non funzionare. "
    "Nei giochi moderni spesso non cambia nulla.")
doc("mpo_off",
    "MPO (Multiplane Overlay) lascia che la scheda video mostri piu' 'livelli' (gioco, video, cursore) "
    "senza ricomporli.",
    "Con alcuni driver e configurazioni multi-monitor l'MPO causa sfarfallii, schermi neri e stutter in "
    "borderless: disattivarlo e' la correzione consigliata anche da NVIDIA in passato.",
    "Un po' piu' di lavoro per la GPU con video e finestre sovrapposte; in giochi in finestra puo' aumentare "
    "leggermente la latenza. Se non hai sfarfallii non serve.")
doc("mpo_full",
    "Come la voce MPO, ma spegne anche gli overlay hardware del driver video.",
    "Da usare solo se la versione normale non ha risolto sfarfallii o stutter in borderless.",
    "Come sopra, con un po' piu' di lavoro per la GPU sul desktop.")
doc("mmcss_games",
    "MMCSS e' il servizio di Windows che da' priorita' a audio e video; ha un profilo 'Games' per i giochi.",
    "Alza la priorita' CPU/GPU dei giochi che si registrano a MMCSS.",
    "Pochi giochi lo usano davvero: spesso nessun effetto. Raramente l'audio puo' gracchiare se un gioco "
    "registrato a MMCSS satura la CPU.")
doc("pcie_aspm",
    "ASPM mette in risparmio energetico il collegamento PCI Express (scheda video, SSD NVMe) quando e' poco usato.",
    "Il 'risveglio' del collegamento richiede tempo: con ASPM attivo possono comparire micro-scatti quando il "
    "carico cambia all'improvviso.",
    "Qualche watt in piu' a riposo. Sui portatili la batteria dura un po' meno.")
doc("gamedvr_policy",
    "Criterio di sistema che blocca Game DVR per tutti gli utenti.",
    "Impedisce che l'app Xbox riattivi la registrazione in background dopo un aggiornamento.",
    "Nessuna registrazione di clip con Game Bar per nessun utente del PC.")
doc("gamebar_shortcut",
    "Il tasto Xbox del controller e Win+G aprono la Game Bar.",
    "Evita aperture accidentali della Game Bar durante il gioco (con i controller succede spesso).",
    "Dovrai aprire la Game Bar dal menu Start se ti serve.")

# ------------------------------------------------------------------ CPU ED ENERGIA
doc("plan_high",
    "Il piano energetico decide quanto velocemente la CPU sale di frequenza e quanto risparmia energia.",
    "'Prestazioni elevate' tiene la CPU pronta a frequenze alte: utile soprattutto su CPU Intel e portatili.",
    "Consumi e temperature a riposo un po' piu' alti. Sui Ryzen recenti il piano Bilanciato e' gia' ottimizzato "
    "da AMD: spesso nessuna differenza.")
doc("plan_ultimate",
    "Piano nascosto di Windows pensato per workstation: elimina ogni micro-risparmio energetico.",
    "Latenza minima nel passaggio da riposo a carico.",
    "Consuma di piu' anche quando il PC non fa niente. Sui portatili sconsigliato.")
doc("core_parking",
    "Il core parking 'spegne' i core della CPU che non servono per risparmiare energia.",
    "Evita il ritardo di riattivazione dei core quando il gioco ne chiede improvvisamente di piu'.",
    "Consumi a riposo leggermente piu' alti. Su CPU AMD con due CCD (es. 7950X3D) puo' interferire con lo "
    "smistamento dei giochi sui core con 3D V-Cache: in quel caso non usarlo.")
doc("power_throttling",
    "Il Power Throttling rallenta i programmi in background per risparmiare energia.",
    "Programmi come Discord, OBS o la musica non vengono rallentati mentre giochi.",
    "Sui portatili la batteria dura meno.")
doc("usb_suspend",
    "La sospensione selettiva USB spegne le porte USB quando i dispositivi sembrano inattivi.",
    "Mouse, tastiera, cuffie e DAC USB non entrano in risparmio: niente micro-blocchi dell'input o audio che si "
    "interrompe.",
    "Qualche watt in piu'; sui portatili la batteria dura un po' meno.")
doc("prio_sep",
    "Win32PrioritySeparation decide quanto tempo CPU dare al programma in primo piano rispetto a quelli in "
    "background.",
    "Il valore 26 (hex) da' piu' tempo CPU alla finestra attiva (il gioco).",
    "Nessun beneficio dimostrato su Windows 11. Programmi in background (stream, registrazione) possono "
    "rallentare. Alternativa a 2A: si escludono a vicenda.")
doc("prio_sep_2a",
    "Come la voce 26, con quanti di tempo brevi e fissi.",
    "Variante preferita nelle community competitive: massimo vantaggio al gioco in primo piano.",
    "Benefici solo aneddotici. OBS e programmi di streaming in background possono perdere fotogrammi.")
doc("sys_resp",
    "SystemResponsiveness e' la percentuale di CPU che MMCSS lascia ai processi normali (default 20%).",
    "Con 10 MMCSS puo' dare piu' CPU alle attivita' multimediali/gioco registrate.",
    "Effetto spesso nullo. In casi rari audio che gracchia con CPU satura.")
doc("dynamic_tick",
    "Il 'dynamic tick' fa scattare il timer di sistema solo quando serve, per risparmiare energia.",
    "Con il timer sempre attivo alcuni utenti riportano una latenza piu' costante.",
    "Modifica il boot: con BitLocker puo' chiedere la chiave di ripristino. Consumi piu' alti e benefici non "
    "misurati, a volte negativi.")
doc("timer_global",
    "Da Windows 10 2004/11 un programma che chiede un timer piu' preciso lo ottiene solo per se'.",
    "Torna il vecchio comportamento globale: serve solo con programmi tipo TimerResolution per forzare 0,5 ms a "
    "tutto il sistema.",
    "Consumi piu' alti; senza un programma che chiede la risoluzione non cambia nulla.")
doc("boost_aggr",
    "La modalita' boost decide quanto velocemente la CPU sale alle frequenze turbo.",
    "'Aggressiva' fa salire subito la CPU al massimo quando arriva il carico.",
    "Temperature un po' piu' alte. Su molti desktop e' gia' il comportamento predefinito.")
doc("min_cpu_100",
    "Lo 'stato minimo del processore' e' la frequenza piu' bassa a cui Windows lascia scendere la CPU.",
    "Al 100% la CPU non scende mai: nessun ritardo di risalita.",
    "Piu' calore e consumi sempre. Sui Ryzen moderni la frequenza la gestisce la CPU stessa: spesso nessun "
    "effetto, e puo' ridurre il margine per il boost.")
doc("idle_off",
    "Gli stati di riposo (C-states) spengono parti della CPU quando non lavora.",
    "Senza riposo la CPU risponde istantaneamente: usato in setup competitivi estremi.",
    "La CPU resta sempre al 100% apparente, scalda e consuma molto. Sui Ryzen riduce il boost e puo' abbassare "
    "gli FPS. Da provare solo con il test prima/dopo.")
doc("hypervisor_off",
    "L'hypervisor di Windows e' la base per Hyper-V, WSL2, Sandbox, VBS e Integrita' della memoria.",
    "Spegnendolo sparisce il piccolo costo della virtualizzazione su ogni operazione del sistema.",
    "Smettono di funzionare WSL2, Docker, macchine virtuali Hyper-V, Sandbox, alcuni emulatori Android e tutte "
    "le protezioni basate su VBS. Con BitLocker puo' chiedere la chiave di ripristino.")

# ------------------------------------------------------------------ MEMORIA E DISCO
doc("mem_compress",
    "Windows comprime parte della RAM invece di spostarla sul disco quando la memoria si riempie.",
    "Con 32 GB o piu' la compressione serve raramente: disattivarla risparmia un po' di lavoro CPU.",
    "Con poca RAM (16 GB o meno) Windows usera' di piu' il file di paging: puo' peggiorare.")
doc("sysmain",
    "SysMain (ex Superfetch) precarica in RAM i programmi che usi spesso.",
    "Meno attivita' di disco in background, utile soprattutto con dischi lenti o RAM piena.",
    "Programmi e giochi possono aprirsi un po' piu' lentamente. Su SSD il beneficio e' minimo.")
doc("wsearch",
    "Windows Search indicizza i file per trovarli subito dal menu Start.",
    "Niente indicizzazione in background che legge il disco mentre giochi.",
    "La ricerca nel menu Start e in Esplora file diventa lenta, soprattutto nei contenuti dei file e in Outlook.")
doc("hibernation",
    "L'ibernazione salva la RAM su disco; l'avvio rapido usa lo stesso meccanismo per 'spegnere' Windows a meta'.",
    "Libera spazio (file grande quanto la RAM) e fa ripartire Windows pulito a ogni accensione.",
    "L'avvio del PC e' qualche secondo piu' lento. Niente ibernazione (sui portatili si usa ancora la "
    "sospensione).")
doc("defender_excl",
    "Microsoft Defender scansiona ogni file che viene aperto.",
    "I giochi caricano migliaia di file mentre giochi: escluderli evita rallentamenti nei caricamenti e nello "
    "streaming degli asset.",
    "I file in quella cartella non vengono controllati in tempo reale: metti solo cartelle di giochi da store "
    "ufficiali (Steam, Epic, Xbox).")
doc("paging_exec",
    "DisablePagingExecutive impedisce a Windows di spostare driver e kernel nel file di paging.",
    "In teoria evita che il kernel debba essere ricaricato dal disco.",
    "Con molta RAM non succede quasi mai comunque: benefici non misurati. Con poca RAM puo' peggiorare.")
doc("prefetch_off",
    "Il Prefetcher prepara in anticipo i file dei programmi che apri spesso.",
    "Tweak famoso dai tempi di Windows XP con gli hard disk.",
    "Su SSD non migliora nulla e i programmi possono aprirsi piu' lentamente. Su Windows 11 e' sconsigliato.")
doc("svchost_split",
    "Windows divide i servizi in tanti processi svchost separati (uno per servizio) se la RAM installata supera "
    "la soglia SvcHostSplitThresholdInKB (predefinita 3,5 GB = 380000 esadecimale). LagDoctor la imposta uguale "
    "alla RAM installata in KB: 8 GB = 800000, 16 GB = 1000000, 32 GB = 2000000, 64 GB = 4000000 (esadecimale, "
    "come li mostra regedit).",
    "Meno processi nel Task Manager e un po' meno RAM usata.",
    "Se un servizio va in crash si porta dietro gli altri dello stesso gruppo. Nessun beneficio misurato nei "
    "giochi.")
doc("ntfs_lastaccess",
    "NTFS puo' salvare l'ora dell'ultimo accesso a ogni file letto.",
    "Quando un gioco legge migliaia di file evita altrettante piccole scritture inutili.",
    "Alcuni programmi di backup o pulizia che usano 'ultimo accesso' non avranno questa informazione.")
doc("ntfs_83",
    "Per compatibilita' con il DOS, Windows crea un secondo nome corto (tipo PROGRA~1) per ogni file.",
    "Nelle cartelle con moltissimi file la creazione dei file e' un po' piu' veloce.",
    "Qualche installer o programma molto vecchio potrebbe non funzionare.")
doc("storage_sense_off",
    "Sensore memoria cancella da solo file temporanei e cestino quando il disco si riempie.",
    "Evita che la pulizia automatica parta mentre giochi.",
    "Dovrai liberare spazio a mano quando serve.")
doc("maintenance_off",
    "La Manutenzione automatica esegue ogni giorno ottimizzazione dei dischi, scansioni e aggiornamenti delle app.",
    "Tweak diffuso per evitare attivita' in background; di solito parte solo con il PC inattivo.",
    "Microsoft consiglia di lasciarla attiva: TRIM degli SSD, pulizie e controlli andranno fatti a mano. "
    "Nessuna prova di benefici nei giochi.")

# ------------------------------------------------------------------ RETE
doc("delivery_opt",
    "Ottimizzazione recapito condivide gli aggiornamenti di Windows con altri PC su Internet (P2P).",
    "La tua connessione non viene usata per inviare aggiornamenti ad altri mentre giochi.",
    "Nessuno: gli aggiornamenti si scaricano normalmente da Microsoft.")
doc("nic_power",
    "Windows puo' spegnere la scheda di rete o metterla in risparmio quando sembra inattiva.",
    "Evita picchi di ping e brevi disconnessioni, soprattutto con il Wi-Fi.",
    "Qualche watt in piu'; sui portatili la batteria dura un po' meno.")
doc("nagle",
    "L'algoritmo di Nagle raggruppa i piccoli pacchetti TCP per inviarne meno.",
    "Nei giochi che usano TCP (alcuni MMO, giochi vecchi) i comandi partono subito invece di aspettare.",
    "La maggior parte degli sparatutto usa UDP: nessun effetto. Un po' piu' di traffico di rete.")
doc("net_throttle",
    "Network Throttling limita il numero di pacchetti di rete elaborati quando riproduci audio o video.",
    "In un test pubblicato e' stato l'unico tweak di rete a ridurre il ping in alcuni giochi.",
    "Piu' carico di interrupt sulla CPU durante grandi download. Effetto variabile da gioco a gioco.")
doc("nic_intmod",
    "L'Interrupt Moderation fa raggruppare alla scheda di rete piu' pacchetti prima di avvisare la CPU.",
    "Ogni pacchetto viene elaborato subito: latenza di rete piu' bassa (Microsoft e Intel lo indicano per la "
    "latenza minima).",
    "Piu' uso della CPU durante download veloci.")
doc("nic_eee",
    "Energy Efficient Ethernet mette in risparmio il collegamento via cavo tra un pacchetto e l'altro.",
    "Evita micro-disconnessioni e picchi di ping che compaiono con alcuni driver.",
    "Pochi watt in piu'.")
doc("nic_flow",
    "Il Flow Control fa mettere in pausa la trasmissione quando il router e' sovraccarico.",
    "Consigliato da molte guide per evitare pause nell'invio.",
    "Nessun beneficio misurato; in reti con switch lenti possono aumentare i pacchetti persi.")
doc("nic_lso",
    "Large Send Offload fa dividere i pacchetti grandi alla scheda di rete invece che alla CPU.",
    "Alcuni driver economici hanno problemi con LSO che causano picchi di ping.",
    "Microsoft dice che gli offload in genere aiutano: piu' uso CPU nei download. Verificalo col test.")
doc("ipv4_pref",
    "Windows preferisce IPv6 quando la rete lo supporta.",
    "Utile se il tuo IPv6 e' instabile o passa da un tunnel lento: le connessioni useranno IPv4.",
    "Se il tuo provider funziona bene in IPv6 non cambia nulla. Serve il riavvio.")
doc("teredo_off",
    "Teredo e' un tunnel che porta IPv6 su reti solo IPv4.",
    "Elimina un adattatore virtuale e traffico inutile se non lo usi.",
    "Alcuni giochi Xbox/Game Pass lo usano per il multiplayer: se l'app Xbox segnala problemi di NAT, annulla.")

# ------------------------------------------------------------------ INTERFACCIA E INPUT
doc("mouse_accel",
    "'Precisione puntatore avanzata' accelera il cursore quando muovi il mouse velocemente.",
    "La mira dipende solo da quanto sposti il mouse, non da quanto veloce: memoria muscolare costante. "
    "Fondamentale negli sparatutto.",
    "Sul desktop il cursore sembra piu' 'lento': puoi alzare la sensibilita' (DPI) del mouse.")
doc("bg_apps",
    "Le app dello Microsoft Store possono restare attive in background.",
    "Meno processi e notifiche in background.",
    "Le app dello Store (es. Posta, Calendario, WhatsApp dallo Store) non aggiornano e non notificano finche' "
    "non le apri.")
doc("transparency",
    "Effetti di trasparenza su menu Start, barra delle applicazioni e finestre.",
    "Meno lavoro per il compositore di Windows sul desktop.",
    "Solo estetica: Windows sembra meno 'moderno'. Nessun effetto nei giochi a schermo intero.")
doc("diagtrack",
    "DiagTrack invia a Microsoft i dati diagnostici e di utilizzo.",
    "Meno attivita' in background e traffico di rete.",
    "Nessuno per l'uso normale. Alcune diagnostiche di Windows Update potrebbero essere meno dettagliate.")
doc("visual_fx",
    "Gli effetti visivi di Windows (Sistema > Impostazioni di sistema avanzate > Prestazioni > Effetti visivi): "
    "animazioni di finestre, menu e barra, dissolvenze, ombre, scorrimento fluido, contenuto delle finestre durante "
    "il trascinamento, rettangolo di selezione trasparente, Peek. Restano attivi 'Smussa gli angoli dei caratteri' "
    "(senza, il testo e' seghettato) e 'Mostra anteprime anziche' icone'.",
    "Finestre e menu si aprono all'istante e il compositore di Windows lavora meno: sui PC deboli o con poca "
    "memoria video Windows e' piu' scattante. Dentro i giochi a schermo intero non cambia niente.",
    "Windows ha un aspetto piu' 'spartano' (niente ombre e animazioni). Annulla rimette ogni casella esattamente "
    "com'era.")
doc("wait_kill_svc",
    "WaitToKillServiceTimeout e' quanto Windows aspetta, allo spegnimento, che i servizi si chiudano da soli "
    "(predefinito 5000 ms, 5 secondi).",
    "Con 2000 ms lo spegnimento e il riavvio sono piu' rapidi quando un servizio e' lento a chiudersi.",
    "Un servizio che stava salvando dati potrebbe essere chiuso prima di finire (raro: i servizi di Windows si "
    "chiudono in meno di 2 secondi). Nessun effetto sui giochi.")
doc("menu_delay",
    "Il ritardo prima che si aprano i sottomenu di Windows (400 ms).",
    "Menu istantanei.",
    "I sottomenu si aprono anche se passi sopra per sbaglio.")
doc("sticky_keys",
    "Premere Shift 5 volte apre la finestra dei Tasti permanenti.",
    "Nei giochi Shift si preme spesso: la finestra ti butta fuori dal gioco.",
    "Se usi i Tasti permanenti per accessibilita', riattivali dalle impostazioni.")
doc("access_keys",
    "Tenere premuto Shift destro 8 secondi apre Filtro tasti; Bloc Num 5 secondi i Tasti di alternanza.",
    "Evita finestre improvvise durante il gioco.",
    "Se usi queste funzioni di accessibilita', riattivale dalle impostazioni.")
doc("keyboard_fast",
    "Ritardo e velocita' con cui un tasto tenuto premuto si ripete.",
    "Movimenti nei menu e nella scrittura piu' rapidi.",
    "Scrivendo puoi ripetere lettere per sbaglio se tieni premuto troppo.")
doc("startup_delay",
    "Windows aspetta qualche secondo prima di avviare i programmi all'avvio.",
    "Il desktop e' pronto prima.",
    "Con molti programmi all'avvio il primo minuto puo' essere piu' pesante.")
doc("notifications_off",
    "Le notifiche popup di Windows e delle app.",
    "Niente popup sopra il gioco (la Modalita' Gioco ne blocca gia' molte).",
    "Non vedrai piu' le notifiche: controllale dal centro notifiche.")
doc("widgets_off",
    "Il pannello Widget (notizie, meteo) resta attivo in background.",
    "Un processo web in meno che scarica contenuti.",
    "Niente pannello Widget.")
doc("edge_bg_off",
    "Edge si precarica all'avvio di Windows e resta in memoria dopo la chiusura.",
    "Libera RAM e CPU se non usi Edge mentre giochi.",
    "Edge si apre un po' piu' lentamente la prima volta.")
doc("recall_off",
    "Recall (solo PC Copilot+) salva e analizza screenshot continui di quello che fai.",
    "Niente cattura e analisi AI in background.",
    "Non potrai cercare nella 'memoria' di Recall.")
doc("copilot_off",
    "Copilot e' l'assistente AI integrato in Windows.",
    "Un componente in meno pronto in background.",
    "Niente Copilot dalla barra delle applicazioni.")
doc("telemetry_policy",
    "Criteri che regolano telemetria, cronologia attivita', ID pubblicitario e app suggerite.",
    "Meno raccolta dati e attivita' in background.",
    "Alcune funzioni 'personalizzate' (suggerimenti, cronologia attivita' tra PC) non funzionano. Con "
    "Windows Home la telemetria non scende sotto il minimo richiesto.")
doc("wersvc",
    "Segnalazione errori raccoglie e invia a Microsoft i dati dei crash.",
    "Dopo un crash Windows non perde tempo a creare il rapporto.",
    "Microsoft non ricevera' i dati dei tuoi crash (meno correzioni mirate) e le soluzioni suggerite dopo un "
    "crash non compariranno.")
doc("spooler", "Lo spooler gestisce le code di stampa.",
    "Un servizio in meno; storicamente ha avuto vulnerabilita' di sicurezza.",
    "NON potrai stampare (nemmeno su PDF con alcune app) finche' non lo riattivi.")

# ------------------------------------------------------------------ SICUREZZA
doc("hvci_off",
    "L'Integrita' della memoria (Isolamento core) usa la virtualizzazione per controllare che ogni driver del "
    "kernel sia legittimo.",
    "E' la parte del VBS che costa di piu': Tom's Hardware ha misurato fino al 5-10% di FPS in meno e 1% low "
    "peggiori in alcuni giochi. Microsoft stessa la indica tra le cose da spegnere per giocare.",
    "Un driver malevolo o vulnerabile puo' essere caricato piu' facilmente. Alcuni anti-cheat recenti possono "
    "richiederla. Puoi riattivarla quando non giochi.")
doc("vbs_off",
    "Il VBS e' la piattaforma di sicurezza basata su virtualizzazione: sopra di essa girano Integrita' della "
    "memoria, Credential Guard e altre protezioni.",
    "Se il VBS resta acceso anche con l'Integrita' della memoria spenta, l'hypervisor continua a girare: "
    "spegnerlo elimina anche quel costo.",
    "Si spengono Credential Guard e le altre protezioni VBS. Se a tenere acceso il VBS sono Hyper-V, WSL o la "
    "Piattaforma macchina virtuale, serve spegnere anche quelli.")
doc("vmp_off",
    "La Piattaforma macchina virtuale e' una funzione di Windows usata da WSL2, app Android e alcune macchine "
    "virtuali.",
    "Accende l'hypervisor anche quando non lo usi: Microsoft consiglia di disattivarla per giocare.",
    "Non funzionano WSL2, Windows Subsystem for Android e alcuni emulatori. Nessun effetto sulla sicurezza.")
doc("virt_off",
    "Tutta la virtualizzazione di Windows in una voce: Integrita' della memoria (Isolamento core), VBS e Credential "
    "Guard, e le Funzionalita' di Windows Hyper-V, Piattaforma macchina virtuale, Piattaforma Windows Hypervisor e "
    "Sandbox. Finche' anche una sola resta accesa, l'hypervisor gira sotto Windows.",
    "L'Integrita' della memoria e' la parte che costa di piu' (Tom's Hardware: fino al 5-10% di FPS e 1% low "
    "peggiori in alcuni giochi); il resto dell'hypervisor aggiunge un piccolo costo a ogni operazione del sistema. "
    "Spegnendo tutto insieme sparisce ogni costo. Microsoft la indica tra le cose da spegnere per giocare.",
    "Meno protezione contro driver e malware a livello kernel. Non funzionano WSL2, Docker, macchine virtuali, "
    "Sandbox ed emulatori Android. Alcuni anti-cheat recenti possono richiedere l'Integrita' della memoria. "
    "Annulla (piu' un riavvio) rimette tutto com'era.")
doc("mitigations_off",
    "Le mitigazioni Spectre/Meltdown proteggono da attacchi che leggono la memoria sfruttando la CPU.",
    "Sulle CPU Intel piu' vecchie (fino alla 9a generazione) possono costare qualche % di prestazioni.",
    "Il PC diventa vulnerabile a questi attacchi, anche da JavaScript nei siti web. Sui Ryzen recenti il "
    "guadagno e' quasi nullo: sconsigliato.")
doc("defender_rt_off",
    "La protezione in tempo reale di Defender controlla ogni file mentre viene aperto.",
    "Elimina del tutto il controllo dei file durante caricamenti e installazioni.",
    "Il PC non e' piu' protetto dai virus in tempo reale. Windows puo' riattivarla da solo. Meglio usare "
    "l'esclusione della sola cartella dei giochi.")
doc("wu_auto_off",
    "Windows Update scarica e installa aggiornamenti da solo.",
    "Niente download o installazioni a sorpresa durante le partite.",
    "Le falle di sicurezza restano aperte finche' non aggiorni a mano. Ricordati di aggiornare almeno una "
    "volta al mese.")
doc("bitlocker_off",
    "BitLocker cifra il disco di sistema.",
    "Sugli SSD con cifratura software elimina un piccolo costo su letture e scritture.",
    "Se il PC viene rubato chiunque puo' leggere i tuoi file. La decifratura richiede tempo; per riattivarla "
    "serve cifrare di nuovo tutto il disco.")
doc("uac_dimmed_off",
    "Quando un programma chiede i permessi di amministratore, Windows oscura lo schermo (desktop sicuro).",
    "Il cambio di desktop puo' far uscire i giochi a schermo intero o minimizzarli.",
    "La finestra di conferma diventa piu' facile da falsificare per un malware.")


# ------------------------------------------------------------------ DRIVER NVIDIA
doc("nvfix_vsync_half",
    "Il V-Sync del Pannello NVIDIA puo' sincronizzare il gioco a 1/2, 1/3 o 1/4 della frequenza del monitor.",
    "Con queste opzioni un monitor da 165 Hz mostra al massimo 82, 55 o 41 FPS: il gioco sembra lento e scattoso. "
    "Torna a 'Usa l'impostazione dell'applicazione'.",
    "Nessuno: e' il valore predefinito del driver.")
doc("nvfix_fpscap_low",
    "'Frequenza fotogrammi massima' limita gli FPS di tutti i giochi.",
    "Un limite molto sotto la frequenza del monitor (es. 60 FPS su 165 Hz) toglie fluidita' ovunque.",
    "Se il limite era voluto (per consumi o rumore), rimettilo per i singoli giochi nel Pannello NVIDIA.")
doc("nvfix_minpower",
    "La 'Modalita' di gestione dell'alimentazione' decide quanto la GPU puo' alzare le frequenze.",
    "'Prediligi consumo minimo' la tiene bassa anche nei giochi: meno FPS.",
    "Nessuno: si torna alla modalita' Normale del driver.")
doc("nvfix_shadercache",
    "La cache shader salva su disco gli shader gia' compilati per riusarli.",
    "Senza cache il gioco ricompila gli shader ogni volta: stutter nei primi minuti e in ogni zona nuova.",
    "Usa qualche GB di disco.")
doc("nvfix_vrr_blocked",
    "L'impostazione 'G-SYNC' per le app puo' consentire, bloccare o forzare la frequenza fissa.",
    "Se nel profilo globale e' bloccata, G-SYNC non funziona in nessun gioco anche se e' acceso.",
    "Nessuno: si torna al valore predefinito ('Consentito').")
doc("nvfix_fxaa",
    "FXAA e' un antialiasing veloce applicato dal driver sopra l'immagine finale.",
    "Forzato su tutti i giochi sfoca testi e HUD e si somma all'antialiasing del gioco.",
    "Nessuno: puoi sempre attivare l'antialiasing nelle impostazioni del gioco.")
doc("nvfix_thread",
    "'Ottimizzazione thread' permette al driver OpenGL di usare piu' core della CPU.",
    "Disattivata, i giochi OpenGL (Minecraft Java, emulatori) perdono FPS.",
    "Nessuno: si torna su Auto.")
doc("nvfix_prerender",
    "I 'frame pre-renderizzati' sono i frame che la CPU prepara in anticipo prima che la GPU li disegni.",
    "Con valori alti ogni tuo input arriva sullo schermo diversi frame dopo: input lag molto piu' alto.",
    "In pochissimi giochi limitati dalla CPU gli FPS possono scendere leggermente.")
doc("nv_lowlat_on",
    "La 'Modalita' bassa latenza' limita la coda di frame preparati in anticipo (Attivata = 1 frame).",
    "Riduce l'input lag quando la GPU e' al 100%. NVIDIA la consiglia nei giochi senza Reflex.",
    "Nei giochi limitati dalla CPU puo' abbassare un po' gli FPS. Nei giochi con NVIDIA Reflex viene ignorata. "
    "'Ultra' non e' impostabile in modo ufficiale: si sceglie dal Pannello.")
doc("nv_shadercache_unlimited",
    "La dimensione massima della cache shader del driver.",
    "Con molti giochi installati la cache non si riempie e gli shader non vengono ricompilati (meno stutter).",
    "Usa piu' spazio su disco (di solito pochi GB, ma puo' crescere).")
doc("nv_refresh_highest",
    "'Frequenza di aggiornamento preferita' decide a che Hz partono i giochi a schermo intero.",
    "Alcuni giochi vecchi partono a 60 Hz: cosi' usano sempre la frequenza massima del monitor.",
    "Nessuno noto.")
doc("nv_power_max",
    "Gestione energia NVIDIA nel profilo globale.",
    "La GPU non scende mai di frequenza: evita cali momentanei nei giochi leggeri o con carico variabile.",
    "Piu' consumi, calore e rumore anche sul desktop e con i video. Meglio impostarla solo per i singoli giochi.")
doc("nv_gsync_windowed",
    "G-SYNC puo' funzionare solo a schermo intero o anche nei giochi in finestra/borderless.",
    "Molti giochi moderni usano il borderless: cosi' anche loro hanno la frequenza variabile.",
    "Alcune app sul desktop (browser, video) possono far sfarfallare lo schermo o cambiare luminosita'.")
doc("nv_vsync_on",
    "Il V-Sync del Pannello NVIDIA sincronizza i frame con il monitor.",
    "Con G-SYNC attivo e FPS limitati sotto la frequenza, elimina il tearing residuo senza aggiungere latenza "
    "(Blur Busters G-SYNC 101). Disattiva il V-Sync dentro i giochi.",
    "SENZA G-SYNC aggiunge input lag e scatti quando gli FPS scendono sotto la frequenza.")
doc("nv_fps_cap",
    "Limite FPS globale del driver.",
    "3 FPS sotto la frequenza del monitor tiene G-SYNC sempre attivo ed evita la latenza del V-Sync al limite.",
    "Nei giochi competitivi senza G-SYNC qualcuno preferisce FPS illimitati. Si applica a tutti i giochi.")
doc("nv_texture_perf",
    "'Filtro texture - Qualita'' sceglie quanto il driver ottimizza il filtro delle texture.",
    "Qualche FPS in piu' nei giochi molto pesanti sulle texture.",
    "Texture leggermente meno nitide a distanza; sulle schede moderne la differenza di FPS e' minima.")

# ------------------------------------------------------------------ DRIVER AMD
doc("amdfix_chill",
    "Radeon Chill abbassa gli FPS quando muovi poco il mouse per risparmiare energia.",
    "I continui cambi di FPS causano micro-stutter e non e' pensato come limitatore (AMD community).",
    "Consumi e calore un po' piu' alti nei giochi tranquilli. Per limitare gli FPS usa FRTC.")
doc("amdfix_esync",
    "Enhanced Sync e' un V-Sync 'intelligente' che si disattiva sotto la frequenza del monitor.",
    "Con FreeSync non serve ed e' una causa segnalata di stutter ogni pochi frame e sfarfallii.",
    "Senza FreeSync potresti vedere un po' di tearing sopra la frequenza del monitor.")
doc("amdfix_vsync_always",
    "'Attesa aggiornamento verticale' e' il V-Sync del driver AMD.",
    "Forzato sempre attivo aggiunge input lag in tutti i giochi; il valore predefinito lascia decidere al gioco.",
    "Nei giochi senza V-Sync proprio potrebbe comparire tearing (con FreeSync quasi mai).")
doc("amdfix_frtc_low",
    "Il Controllo obiettivo frequenza fotogrammi (FRTC) limita gli FPS di tutti i giochi.",
    "Un limite molto sotto la frequenza del monitor toglie fluidita' ovunque.",
    "Se il limite era voluto, impostalo per i singoli giochi in Adrenalin.")
doc("amdfix_mlaa",
    "L'antialiasing morfologico e' un filtro del driver applicato sopra l'immagine finale.",
    "Sfoca testi e HUD e costa FPS in tutti i giochi.",
    "Nessuno: usa l'antialiasing del gioco.")
doc("amd_antilag_on",
    "Radeon Anti-Lag sincronizza CPU e GPU per ridurre la coda di frame.",
    "Meno input lag quando la GPU e' al limite.",
    "Nei giochi limitati dalla CPU l'effetto e' minimo. La vecchia variante Anti-Lag+ causava ban VAC in CS2 ed "
    "e' stata ritirata; nei giochi con Anti-Lag 2 integrato attiva quello dal menu del gioco.")
doc("amd_boost_off",
    "Radeon Boost abbassa dinamicamente la risoluzione durante i movimenti veloci.",
    "Immagine sempre nitida, niente scie con il TAA.",
    "Nei giochi supportati perdi i FPS extra durante i movimenti veloci.")
doc("amd_afmf_off",
    "AMD Fluid Motion Frames genera frame intermedi a livello di driver.",
    "Nei giochi competitivi la reattivita' reale conta piu' degli FPS mostrati: AFMF aggiunge latenza.",
    "Nei giochi single-player pesanti perdi la fluidita' visiva extra.")
doc("amd_fps_cap",
    "FRTC impostato 3 FPS sotto la frequenza del monitor.",
    "Mantiene FreeSync sempre attivo e riduce consumi e latenza da V-Sync.",
    "Nei giochi competitivi senza FreeSync qualcuno preferisce FPS illimitati.")


# ------------------------------------------------------------------ DEBLOAT
_DEB_WHY = ("Meno processi, aggiornamenti dello Store e attivita' in background; menu Start piu' pulito. Il "
            "guadagno in FPS e' piccolo: serve soprattutto a togliere cose che girano senza motivo.")
_DEB_CONS = ("Nessuno per il sistema (app classificata 'safe'). La rimozione e' solo per il tuo utente: 'Annulla' la "
             "reinstalla dalla copia di Windows, oppure la riscarichi dal Microsoft Store.")
for _id, _cosa in [
        ("app_bing", "Meteo, Notizie, Sport, Finanza e le altre app Bing preinstallate: aggiornano contenuti dalla rete."),
        ("app_solitaire", "Microsoft Solitaire Collection: giochi di carte con pubblicita' e accesso Xbox."),
        ("app_candy", "Giochi e app promozionali (Candy Crush, TikTok, Spotify, Netflix, LinkedIn...) che Windows "
                      "installa o 'segnaposto' nel menu Start."),
        ("app_clipchamp", "Clipchamp: editor video di Microsoft basato su web."),
        ("app_officehub", "L'app 'Microsoft 365' che pubblicizza Office (non e' Office)."),
        ("app_getstarted", "Suggerimenti: l'app che mostra consigli su Windows."),
        ("app_feedback", "Hub di Feedback: invia segnalazioni a Microsoft."),
        ("app_maps", "Mappe di Windows, che puo' aggiornare le mappe offline in background."),
        ("app_todo", "Microsoft To Do: elenchi di attivita' collegati all'account Microsoft."),
        ("app_powerautomate", "Power Automate Desktop: automazioni per uffici."),
        ("app_devhome", "Dev Home: pannello per sviluppatori, dismesso da Microsoft."),
        ("app_mixedreality", "Portale realta' mista, 3D Viewer, 3D Builder e Print 3D: per visori e modelli 3D."),
        ("app_teams", "Microsoft Teams (versione personale) preinstallato, che parte con Windows."),
        ("app_skype_people", "Skype, Contatti, Posta e Calendario vecchi, Messaggi: app dismesse o sostituite."),
        ("app_family", "Microsoft Family: controllo genitori per gli account dei figli."),
        ("app_journal_sway", "Journal, Sway, OneNote (app dello Store) e Power BI."),
        ("app_zunevideo", "Film e TV: il vecchio lettore video (il Lettore multimediale resta)."),
        ("app_xboxold", "Xbox Console Companion: la VECCHIA app Xbox, sostituita dalla nuova app Xbox."),
        ("app_pcmanager", "Microsoft PC Manager e AI Hub: 'ottimizzatore' e vetrina AI di Microsoft."),
        ("app_cortana", "Cortana: assistente vocale dismesso."),
        ("app_alarms_recorder", "Sveglie e orologio, Registratore di suoni."),
        ("app_stickynotes", "Sticky Notes: note adesive sul desktop."),
        ("app_outlook_new", "Il nuovo Outlook gratuito preinstallato."),
        ("app_phonelink", "Collegamento al telefono: mostra notifiche, SMS e foto dello smartphone sul PC.")]:
    doc(_id, _cosa, _DEB_WHY, _DEB_CONS)
D["app_family"]["problemi"] = "Se usi il controllo genitori per gli account dei figli, non rimuoverla. " + _DEB_CONS
D["app_phonelink"]["problemi"] = "Se usi lo smartphone collegato al PC, non rimuoverla. " + _DEB_CONS
D["app_teams"]["perche"] = "Teams personale parte con Windows e resta in memoria: toglierlo libera RAM e CPU. " + _DEB_WHY
D["app_xboxold"]["problemi"] = ("Nessuno: la nuova app Xbox, la Game Bar e i servizi Xbox per Game Pass NON vengono "
                                "toccati. " + _DEB_CONS)
doc("app_onedrive",
    "OneDrive sincronizza file e cartelle (spesso Desktop, Documenti, Immagini) con il cloud e parte con Windows.",
    "Durante la sincronizzazione usa disco, rete e CPU: se capita mentre giochi puo' causare stutter e picchi di ping.",
    "Smette il backup automatico nel cloud. I file gia' presenti nella cartella OneDrive restano sul PC. "
    "'Annulla' lo reinstalla con winget.")

# ------------------------------------------------------------------ TIMER RESOLUTION
doc("timer_res",
    "Il timer di Windows decide ogni quanto il sistema 'si sveglia' per gestire i thread: di default ogni 15,6 ms, "
    "a meno che un programma non chieda di piu'. LagDoctor lo porta a 0,5 ms con un piccolo processo invisibile che "
    "parte a ogni accesso (e attiva GlobalTimerResolutionRequests, necessario da Windows 11).",
    "Molti giochi chiedono gia' un timer di 1 ms: a 0,5 ms i limitatori di FPS e le attese brevi sono piu' precisi "
    "e il frame pacing puo' essere piu' regolare. E' uno dei tweak piu' famosi delle community competitive.",
    "Piu' consumi a riposo (la CPU si sveglia piu' spesso). L'effetto dipende dal PC e dal gioco: chi ha misurato "
    "consiglia di provarlo, e in alcuni casi 0,5 ms e' meno preciso di valori come 0,507 ms. Verificalo con il "
    "test Prima/Dopo. Serve il riavvio per GlobalTimerResolutionRequests.")

# ------------------------------------------------------------------ IMPOSTAZIONI DI WINDOWS
doc("power_mode_best",
    "Impostazioni > Sistema > Alimentazione > 'Modalita' risparmio energia' (Bilanciata / Prestazioni migliori).",
    "Con il piano Bilanciato rende la CPU piu' reattiva ad alzare le frequenze.",
    "Consumi leggermente piu' alti. Funziona solo con il piano Bilanciato.")
doc("start_web_off",
    "La ricerca del menu Start mostra anche risultati web di Bing.",
    "La ricerca diventa solo locale: piu' veloce e senza processi web in background.",
    "Non vedrai piu' risultati web nel menu Start.")
doc("wu_active_hours",
    "Le 'ore attive' di Windows Update: in quella fascia Windows non riavvia il PC da solo.",
    "Evita riavvii o notifiche di riavvio durante le sessioni di gioco serali.",
    "Gli aggiornamenti che richiedono il riavvio verranno installati di notte o quando riavvii tu.")
doc("usb_notify_off",
    "Impostazioni > Bluetooth e dispositivi > USB > notifiche per problemi di connessione USB.",
    "Niente popup sopra il gioco se un dispositivo USB ha un problema momentaneo.",
    "Non sarai avvisato se un dispositivo USB funziona male (es. porta con poca alimentazione).")
doc("metered_drivers",
    "Quando colleghi un dispositivo, Windows puo' scaricare da solo l'app del produttore (Razer, Logitech, ecc.).",
    "Evita che vengano installati software di periferiche che restano in background (alcuni causano stutter).",
    "Le app dei produttori andranno installate a mano se ti servono.")
doc("mouse_pointer_6",
    "La velocita' del puntatore di Windows (cursore 6/11).",
    "Al valore neutro il movimento del mouse non viene moltiplicato: utile nei giochi che non usano il 'raw input'.",
    "Se sul desktop il cursore ti sembra lento, alza i DPI del mouse invece della velocita' di Windows.")

# ------------------------------------------------------------------ NON AFFIDABILI (miti)
# Per queste voci:  cosa = cosa fa  |  perche = quando potrebbe aiutare  |  problemi = perche' e' meglio lasciarlo spento
doc("myth_pagefile_off",
    "Elimina il file di paging: Windows puo' usare solo la RAM fisica.",
    "Quasi mai. Su PC con moltissima RAM e un SSD piccolo libera qualche GB di spazio.",
    "Quando la RAM si riempie i giochi vanno in crash invece di rallentare; molti giochi moderni lo richiedono "
    "anche con 32 GB. Nessun guadagno di FPS misurato.")
doc("myth_hpet_on",
    "Obbliga Windows a usare il timer HPET della scheda madre al posto di quello moderno della CPU.",
    "Solo in rari casi di bug specifici di vecchie piattaforme o software di misura.",
    "Leggere l'HPET e' molto lento: aumenta la latenza e peggiora FPS e stutter sui PC moderni (test Blur Busters "
    "e community).")
doc("myth_autotuning_off",
    "Blocca la dimensione della finestra di ricezione TCP.",
    "Con router o reti molto vecchie e difettose che gestiscono male l'auto-tuning.",
    "Limita la velocita' di download di giochi e aggiornamenti; il ping dei giochi (UDP) non cambia.")
doc("myth_largecache",
    "Mette la cache dei file di sistema in modalita' server.",
    "Su file server che servono molti file in rete.",
    "Su un PC da gioco toglie RAM ai programmi.")
doc("myth_trim_off",
    "Disattiva il TRIM, il comando che dice all'SSD quali dati sono stati cancellati.",
    "Solo per diagnosticare rari problemi di compatibilita' di vecchi SSD.",
    "L'SSD rallenta col tempo e si consuma di piu'.")
doc("myth_defrag_off",
    "Disattiva l'ottimizzazione pianificata dei dischi.",
    "Su hard disk con dati che non cambiano mai.",
    "Sugli SSD l'ottimizzazione e' il TRIM (non una deframmentazione): disattivarla li rallenta col tempo.")
doc("myth_qos",
    "Imposta a 0 il limite di banda 'riservata' del QoS di Windows.",
    "Nessun caso noto per i giochi.",
    "Windows non riserva banda se nessun programma usa il QoS: il tweak non cambia niente (innocuo ma inutile).")
doc("myth_irq8",
    "Aumenta la priorita' dell'interrupt dell'orologio di sistema (IRQ 8).",
    "Nessuno su Windows moderni.",
    "Su Windows 2000/XP e successivi la chiave viene ignorata: innocuo ma inutile.")
doc("myth_conservative_swap",
    "Chiede a Windows di usare meno il file di paging.",
    "Nessuno su Windows 10/11.",
    "Chiave dei tempi di Windows XP, ignorata dai Windows moderni: innocua ma inutile.")
doc("myth_dns",
    "Usa i DNS di Cloudflare (1.1.1.1) invece di quelli del tuo provider.",
    "Se i DNS del provider sono lenti o bloccano siti, l'apertura dei siti e la connessione iniziale ai server "
    "possono essere un po' piu' rapide.",
    "Il DNS serve solo a trovare l'indirizzo del server all'inizio: NON cambia il ping durante la partita.")


# ------------------------------------------------------------------ IMPOSTAZIONI LETTE DAL DRIVER (pagina "Driver video")
# nome della riga -> cosa fa / valore consigliato e perche' / possibili problemi
DRIVER_DOCS = {}


def ddoc(name, cosa, consigliato, problemi):
    DRIVER_DOCS[name] = {"cosa": cosa, "perche": consigliato, "problemi": problemi}


# NVIDIA
ddoc("Modalita' bassa latenza",
     "Decide quanti frame la CPU puo' preparare in anticipo prima che la GPU li disegni. Disattivata = decide il "
     "gioco; Attivata = 1 frame; Ultra = il driver sincronizza la CPU per consegnare il frame 'appena in tempo'.",
     "Attivata nei giochi SENZA NVIDIA Reflex quando la GPU e' vicina al 100%: meno input lag (guida ufficiale "
     "NVIDIA). Nei giochi con Reflex attiva Reflex nel gioco: il driver viene ignorato.",
     "Ultra puo' abbassare gli FPS quando il limite e' la CPU e non ha effetto nei giochi DirectX 12. Con la GPU "
     "poco carica non cambia nulla.")
ddoc("Sincronizzazione verticale (V-Sync)",
     "Sincronizza l'invio dei frame con il refresh del monitor per eliminare il tearing (immagine 'tagliata').",
     "Con G-SYNC: Attivato nel Pannello e disattivato nel gioco, insieme a un limite FPS 3 sotto la frequenza "
     "(Blur Busters). Senza G-SYNC: 'Usa l'impostazione dell'applicazione' e scegli nel gioco.",
     "Senza G-SYNC aggiunge input lag e scatti quando gli FPS scendono sotto la frequenza. Le opzioni 1/2, 1/3, "
     "1/4 dimezzano (o peggio) gli FPS massimi. 'Veloce' (Fast Sync) puo' causare stutter con G-SYNC.")
ddoc("Frequenza fotogrammi massima",
     "Limite di FPS imposto dal driver a tutti i giochi.",
     "Disattivata, oppure 3 FPS sotto la frequenza del monitor se usi G-SYNC (es. 162 su 165 Hz): G-SYNC resta "
     "sempre attivo e si evita la latenza del V-Sync.",
     "Un limite basso (es. 60 su un monitor 165 Hz) toglie fluidita' a tutto. Nei competitivi senza G-SYNC c'e' chi "
     "preferisce FPS illimitati.")
ddoc("Modalita' di gestione dell'alimentazione",
     "Quanto la GPU puo' scendere di frequenza per risparmiare energia.",
     "Normale nel profilo globale; 'Prediligi prestazioni massime' solo nei profili dei giochi che hanno cali "
     "quando la GPU 'si addormenta' (giochi leggeri, esports).",
     "'Prestazioni massime' globale: consumi, calore e rumore piu' alti anche sul desktop. 'Consumo minimo': meno "
     "FPS nei giochi.")
ddoc("Cache shader",
     "Spazio su disco dove il driver salva gli shader gia' compilati, cosi' non li ricompila a ogni avvio.",
     "Attiva, con dimensione predefinita, 10 GB o Illimitata se hai spazio su SSD: meno stutter da compilazione "
     "shader.",
     "Disattivata o troppo piccola: stutter nei primi minuti di gioco e in ogni zona nuova. Illimitata occupa piu' "
     "spazio su disco.")
ddoc("G-SYNC",
     "La frequenza variabile: il monitor si adatta agli FPS del gioco, niente tearing e niente scatti da V-Sync.",
     "Attivo se il monitor e' G-SYNC o G-SYNC Compatible. 'Schermo intero e finestra' se giochi in borderless.",
     "In modalita' finestra alcune app sul desktop possono far sfarfallare lo schermo o cambiarne la luminosita'.")
ddoc("Tecnologia monitor / G-SYNC per le app",
     "Permette o blocca G-SYNC per le applicazioni (nel profilo globale vale per tutte).",
     "Consentito.",
     "'Non consentito', 'Forzato disattivato' o 'Frequenza fissa' disattivano G-SYNC in tutti i giochi anche se e' "
     "acceso.")
ddoc("Frequenza di aggiornamento preferita",
     "Decide a che frequenza partono i giochi a schermo intero esclusivo.",
     "'La piu' alta disponibile': alcuni giochi, soprattutto vecchi, altrimenti partono a 60 Hz.",
     "Nessuno noto; nei giochi in finestra/borderless non ha effetto (vale la frequenza di Windows).")
ddoc("Filtro texture - Qualita'",
     "Quanto il driver ottimizza il filtro delle texture (nitidezza a distanza contro prestazioni).",
     "Qualita' (predefinito) o Prestazioni elevate se cerchi ogni FPS: sulle schede moderne la differenza e' "
     "minima.",
     "Prestazioni elevate: texture un po' meno nitide a distanza. Alta qualita': costo minimo di FPS.")
ddoc("Ottimizzazione thread",
     "Permette al driver OpenGL di usare piu' core della CPU.",
     "Auto (predefinito).",
     "Disattivata: meno FPS nei giochi OpenGL (Minecraft Java, emulatori). Raramente qualche gioco OpenGL vecchio "
     "preferisce Disattivata.")
ddoc("FXAA forzato",
     "Antialiasing veloce applicato dal driver sopra l'immagine finale di ogni gioco.",
     "Disattivato: usa l'antialiasing (TAA, DLSS, DLAA) del gioco.",
     "Forzato sfoca testi e HUD e si somma all'antialiasing del gioco.")
ddoc("Limite FPS per app inattive",
     "Limita gli FPS delle applicazioni che non sono in primo piano (funzione recente dell'app NVIDIA).",
     "Va bene attivo: riduce consumi e calore quando il gioco e' in secondo piano.",
     "Se giochi in finestra mentre usi un altro monitor, il gioco puo' essere considerato 'inattivo' e limitato.")

# AMD
ddoc("Radeon Anti-Lag",
     "Sincronizza CPU e GPU per ridurre la coda di frame e quindi l'input lag.",
     "Attivo nei giochi in cui la GPU e' al limite. Nei giochi con Anti-Lag 2 integrato attiva quello dal menu "
     "del gioco.",
     "Effetto minimo quando il limite e' la CPU. La vecchia variante Anti-Lag+ causava ban VAC in CS2 ed e' stata "
     "ritirata da AMD; l'Anti-Lag attuale e Anti-Lag 2 sono considerati sicuri.")
ddoc("Radeon Chill",
     "Abbassa gli FPS quando muovi poco il mouse o la scena e' statica, per risparmiare energia e calore.",
     "Disattivato per giocare; per limitare gli FPS usa il Controllo obiettivo frequenza fotogrammi.",
     "I continui cambi di FPS causano micro-stutter e risposta meno costante del mouse.")
ddoc("Radeon Boost",
     "Abbassa la risoluzione durante i movimenti veloci della visuale per guadagnare FPS.",
     "Disattivato se vuoi immagine sempre nitida; attivo solo se ti servono FPS nei giochi supportati.",
     "Immagine meno nitida e scie (ghosting) nei giochi con TAA.")
ddoc("Radeon Image Sharpening",
     "Filtro di nitidezza applicato all'immagine finale.",
     "A piacere: costo prestazionale minimo (utile con FSR o risoluzione bassa).",
     "Troppo alto crea bordi 'seghettati' e rumore.")
ddoc("Enhanced Sync",
     "V-Sync 'intelligente' che si disattiva quando gli FPS scendono sotto la frequenza del monitor.",
     "Disattivato se hai un monitor FreeSync (non serve); puo' avere senso solo senza FreeSync.",
     "Con FreeSync e' segnalato come causa di stutter ogni pochi frame, sfarfallii e schermo nero.")
ddoc("Attesa aggiornamento verticale (V-Sync)",
     "Il V-Sync del driver AMD.",
     "'Disattivata, se non specificato dall'app' (predefinito): decide il gioco.",
     "'Sempre attivata' aggiunge input lag in tutti i giochi; 'Sempre disattivata' puo' causare tearing senza "
     "FreeSync.")
ddoc("Controllo obiettivo frequenza fotogrammi",
     "Limite di FPS imposto da Adrenalin (FRTC).",
     "Disattivato, oppure 3 FPS sotto la frequenza del monitor con FreeSync.",
     "Un limite basso toglie fluidita' a tutti i giochi.")
ddoc("Antialiasing",
     "Come il driver tratta l'antialiasing dei giochi: usarlo, migliorarlo o sostituirlo.",
     "'Usa le impostazioni dell'app'.",
     "'Sostituisci' costa prestazioni e spesso non funziona in DirectX 12 / Vulkan.")
ddoc("Antialiasing morfologico (MLAA)",
     "Antialiasing applicato dal driver come filtro sull'immagine finale.",
     "Disattivato.",
     "Sfoca testi e HUD e costa qualche FPS in tutti i giochi.")
ddoc("Radeon Super Resolution",
     "Ingrandisce con FSR 1 i giochi che girano a risoluzione piu' bassa dello schermo (solo schermo intero).",
     "Attivo solo se abbassi apposta la risoluzione per avere piu' FPS; altrimenti non fa nulla.",
     "Immagine meno nitida della risoluzione nativa.")
ddoc("AMD Fluid Motion Frames (AFMF)",
     "Generazione di frame del driver: inserisce frame intermedi per aumentare gli FPS mostrati.",
     "Disattivato nei giochi competitivi; attivo a piacere nei single-player pesanti.",
     "Piu' input lag, possibili artefatti; gli FPS mostrati non corrispondono alla reattivita' reale.")


def get(tid):
    return D.get(tid)
