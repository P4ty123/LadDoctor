# LagDoctor

Trova la causa degli stutter e del lag nei giochi su Windows 10/11 e la corregge.

- **Analizza gioco**: registra una partita con PresentMon e classifica ogni stutter (CPU, GPU, disco, RAM, VRAM,
  driver, shader, V-Sync...), collegandolo alle impostazioni del PC che lo causano.
- **Ottimizzazioni**: oltre 150 impostazioni di Windows, NVIDIA e AMD, ognuna con spiegazione, rischio, backup e
  pulsante Annulla.
- **Game mode**: quando apri un gioco, Windows si concentra su di lui (priorita' CPU/GPU/rete, servizi e app inutili
  fermati, affinita' dei core decisa in base al processore, metodo sicuro per i giochi con anti-cheat). Quando lo
  chiudi tutto torna com'era.
- **Scansione completa** del sistema, sensori della scheda video in tempo reale, autodiagnosi di sola lettura.

## Installazione

1. Vai su [Releases](../../releases/latest) e scarica `LagDoctor-Setup-X.Y.Z.exe`.
2. Avvialo. Windows potrebbe mostrare "Windows ha protetto il PC" (il programma non ha una firma digitale a
   pagamento): clicca **Ulteriori informazioni** e poi **Esegui comunque**.
3. Gli aggiornamenti arrivano da soli: LagDoctor avvisa quando c'e' una versione nuova (pulsante **Aggiornamenti**).

I dati (backup delle modifiche, report, configurazione) sono in `C:\ProgramData\LagDoctor` e restano anche dopo
aggiornamenti e reinstallazioni. Alla disinstallazione LagDoctor chiede se annullare tutte le modifiche.

## Avvio dal codice (senza installare)

Doppio clic su `AVVIA.bat` (installa Python e psutil se mancano).

## Come viene pubblicata una nuova versione

1. Si aggiorna `__version__` in `lagdoctor/__init__.py` e il file `NOVITA.md`, e si carica la modifica su `main`.
2. GitHub Actions (`.github/workflows/release.yml`) vede che quella versione non e' ancora pubblicata: costruisce gli
   eseguibili con PyInstaller e l'installatore con Inno Setup, calcola l'impronta SHA-256 e pubblica la Release
   `vX.Y.Z`. Il programma la trova e si aggiorna.

## Licenze

PresentMon (incluso in `strumenti/`) e' di Intel, licenza MIT: vedi `strumenti/PresentMon-LICENSE.txt`.
Il carattere Inter (in `lagdoctor/ui/fonts/`) e' distribuito con licenza SIL Open Font License 1.1: vedi `lagdoctor/ui/fonts/OFL.txt`.
