🇬🇧 [English](README.md) | 🇭🇺 [Magyar](README.hu.md)

[![CI](https://github.com/miklosbagi/invforge/actions/workflows/ci.yml/badge.svg)](https://github.com/miklosbagi/invforge/actions/workflows/ci.yml)
[![CodeQL](https://github.com/miklosbagi/invforge/actions/workflows/codeql.yml/badge.svg)](https://github.com/miklosbagi/invforge/actions/workflows/codeql.yml)
[![Latest release](https://img.shields.io/github/v/release/miklosbagi/invforge)](https://github.com/miklosbagi/invforge/releases/latest)
[![Docker pulls](https://img.shields.io/docker/pulls/miklosbagi/invforge)](https://hub.docker.com/r/miklosbagi/invforge)
[![Image size](https://img.shields.io/docker/image-size/miklosbagi/invforge/latest)](https://hub.docker.com/r/miklosbagi/invforge)
[![License](https://img.shields.io/github/license/miklosbagi/invforge)](LICENSE)
[![Maintained](https://img.shields.io/badge/maintained-yes-green.svg)](https://github.com/miklosbagi/invforge/graphs/commit-activity)

# InvForge

Egy hamis Modbus TCP inverter/BESS (akkumulátoros energiatároló rendszer),
Modbus-alapú kliensek (NUT driverek, monitorozó eszközök, bármi más)
teszteléséhez, valódi hardver nélkül. Eleve több gyártót támogat: a
Modbus/forgatókönyv/vezérlő-API motor gyártófüggetlen
(`invforge/core/`), és minden gyártó regisztertérképe, mértékegységei és
forgatókönyv-fájljai a saját profiljában élnek
(`invforge/profiles/<gyártó>/`).

Eredetileg egy egygyártós (Sigenergy) szimulátorból lett kiemelve és
általánosítva, amelyet a [sigennut](https://github.com/miklosbagi/sigennut)
projekthez építettünk; ide az első profilként került át
(`invforge/profiles/sigenergy/`), hogy ugyanez a szimulátor bővíthető
legyen más inverter/BESS családokkal is (Deye/SunSynk, Victron GX,
Growatt, SolarEdge, ...), ahogy azokra a sigennut által támogatott NUT
driver-fejlesztésnek, vagy más felhasználóknak szüksége lesz.

## Gyorsindítás

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m invforge --vendor sigenergy --firmware V100R001C21SPC116 \
    --modbus-port 5020 --control-port 8080 [--scenario <név>]
```

A `--firmware` elhagyható, ha egy gyártóhoz pontosan egy megerősített
firmware tartozik (mint jelenleg a Sigenergy esetében) — ekkor önmagában
a `--vendor sigenergy` is feloldja azt. Amint egy második firmware is
regisztrálva lesz egy gyártóhoz, a `--firmware` kötelezővé válik, és egy
ismeretlen érték esetén a program egy egyértelmű listával lép ki az
elérhető opciókról, ahelyett hogy csendben találgatna.

Ezután irányíts bármilyen Modbus TCP klienst a `127.0.0.1:5020` címre —
ugyanazokkal az unit/regiszter-címekkel, mint amelyeket a profil modellezett
valódi eszköz használ. A Sigenergy SigenStor a 247-es unitot (plant) és az
1-es unitot (inverter stringek) használja.

## HTTP vezérlő API (alapértelmezetten a 8080-as porton)

A tesztfuttató távoli vezérlőcsatornája — HTTP+JSON, nem gRPC (ez a
forgalom alacsony áteresztőképességű, egy fogyasztós, és így ingyen
`curl`-ozható marad egy elbukott teszt debuggolása közben).

- `GET /health` — Docker healthcheckekhez.
- `GET /scenarios` — `{"library": {name: relative_path, ...},
  "generators": [<elnevezési-minta>, ...]}` a futó profilhoz.
- `POST /scenario {"name": "...", "speed": 1.0}` — betölt és elindít egy
  megnevezett forgatókönyv időbeli lejátszását (valós idő, `speed`-del
  skálázva), a végén a forgatókönyv hosszánál ismétlődve. A `name` először
  a statikus YAML-könyvtárban keres egyezést, majd — ha ott nincs találat
  — a paraméteres rámpa-generátorban (lásd lentebb). Egyben törli a
  `/fault` végponton kényszerített felülbírálást is, visszaállítva
  "auto"-ra.
- `POST /fault {"connectivity": "offline"|"online"|"auto"}` — igény szerinti,
  kapcsolat szintű hibainjektálás: kényszeríti a Modbus TCP figyelőt
  offline/online állapotba, vagy visszaállítja forgatókönyv-vezérelt
  ("auto") módra. Ez a valódi socketet is megszakítja (a már kapcsolódott
  klienseket is), nem csak egy regiszterszintű Modbus kivételt ad vissza.
  Ragadós (sticky): elsőbbséget élvez egy forgatókönyv saját `offline:`
  ablakaival szemben, amíg törlésre nem kerül, vagy új forgatókönyv nem
  töltődik be.
- `POST /state {"registers": {"30014": 50, "1:30500": "..."}}` —
  **azonnali felülírás**: közvetlenül beleír az adattárba, és lefagyasztja
  az időzítőt (`mode: "manual"`), így semmi nem írja felül a következő
  `/scenario` vagy `/state` hívásig. Egy önmagában álló cím-kulcs a profil
  alapértelmezett unitját célozza; a `"<unit>:<cím>"` forma explicit módon
  egy másik unitot céloz. Az értékek nyers (raw) huzalértékek (egyszerű
  egész szám egyregiszteres mezőknél, `[hi, lo]` az S32/U32 mezőknél) —
  ugyanaz a konvenció, mint a forgatókönyv YAML-fájloknál.
- `GET /state` — minden ismert regiszter aktuális nyers és dekódolt
  értéke minden uniton, plusz az aktuális mód/forgatókönyv/sebesség/
  kapcsolat-állapot — debughoz.

## Hogyan működik

- `invforge/core/registers.py` — gyártófüggetlen regisztermodell
  (cím/darabszám/adattípus/szorzó/mértékegység/dinamikus), plusz
  kódoló/dekódoló segédfüggvények.
- `invforge/core/profile.py` — egy `Profile` egybefogja egy adott
  gyártó+firmware regiszterlistáját, alapértelmezett unitját és
  forgatókönyv-fájljainak könyvtárát. A regiszter-címek/elrendezések a
  valóságban firmware-verziónként eltérhetnek (lásd
  `nut-sigenergy/docs/driver-coding-standards.md` megjegyzését a
  Sigenergy saját firmware-történetéről), ezért egy `Profile` egyetlen
  konkrét firmware-hez tartozik, nem egy egész gyártóhoz — lásd lentebb
  az "Új gyártói profil hozzáadása" részt.
- `invforge/core/scenario.py` — betölt egy forgatókönyv YAML-t (`static`
  / `timeseries` / `exceptions`), és a numerikus regisztereket lineárisan
  interpolálja az egymást követő időbeli minták között, nyers
  huzalérték-térben.
- `invforge/core/server.py` — egy pymodbus TCP szerver, uniток
  azonosítónként egy-egy adattár-blokkal, ahogy a profil definiálja. Egy
  háttérszál a `dynamic=True` jelölésű regisztereket valós idejű
  ütemben (`--speed` szorzó, `--tick` intervallum) lépteti tovább,
  függetlenül a kérések kiszolgálásától — ugyanúgy, ahogy egy valódi
  eszköz telemetria-ciklusa is független attól, hogy egy kliens éppen mikor
  kérdez le adatot. A forgatókönyv hosszának leteltével visszaugrik
  `t=0`-ra.
- `invforge/core/generator.py` — paraméteres rámpa-forgatókönyv generátor
  (lásd lentebb a "Paraméteres rámpa-forgatókönyvek" részt); csak
  gyártófüggetlen mechanizmus, a tényleges rámpaépítő logikát egy profil
  a `Profile.ramp_builder`-en keresztül adja meg.
- `invforge/core/connectivity.py` — az élő Modbus TCP figyelő
  online/offline életciklusát kezeli (lásd lentebb az "Offline /
  kapcsolatmegszakítás szimuláció" részt).
- `invforge/core/control_api.py` — a fenti FastAPI vezérlőfelület.
- `invforge/profiles/<gyártó>/firmwares/<firmware>/` — egy
  `registers.py` (a `RegisterDef` lista), egy `scenarios/` könyvtár, és
  egy `__init__.py`, amely exportálja a `PROFILE: Profile`-t. Lásd
  `invforge/profiles/sigenergy/firmwares/V100R001C21SPC116/` mint
  referenciapélda.

A nem definiált regiszterek Modbus-olvasása ugyanúgy elbukik, mint egy
valódi eszköznél (illegal data address) — a definiálatlan regisztereknél
ezt magától az adattár cím-tartomány-ellenőrzése kezeli; egy forgatókönyv
`exceptions:` blokkja bármely más címet is megjelölhet mindig-illegálisnak,
annak teszteléséhez, hogy egy kliens helyesen kezeli-e egy valódi firmware
furcsa 400-as válaszait.

Néhány valódi firmware bizonyos címeket kifejezetten egy olvasás *kezdő*
címeként utasít el — egy létező, tartományon belüli regiszter, amely
egyszerűen nem lehet egy Modbus-kérés első címe, míg egy máshonnan induló,
de ezt is lefedő tartomány-olvasás rendben működik. Ezt valódi Sigenergy
hardveren empirikusan megerősítettük (`30281`-es regiszter). Ez egy
állandó, firmware-specifikus tulajdonság, nem forgatókönyv-adat, ezért
külön van modellezve: `Profile.non_anchor_addresses` (címek egy
frozenset-je), amelyet minden blokk érvényesít, függetlenül attól, melyik
forgatókönyv van éppen betöltve. A teljes történethez lásd
`invforge/profiles/sigenergy/firmwares/V100R001C21SPC116/registers.py`
modul-docstringjét.

A Sigenergy regisztertáblázata szándékosan nem a teljes, ~280 bejegyzésből
álló specifikáció — a pontos terjedelemért lásd ugyanazt a
modul-docstringet (az UPS/akkumulátor-tartalék driver szempontjából
releváns részhalmaz, megegyezve azzal, amit a validáláshoz használt
konkrét valódi telepítés ténylegesen tartalmaz).

## Új gyártói profil hozzáadása

1. Hozd létre az
   `invforge/profiles/<gyártó>/firmwares/<firmware>/registers.py`
   fájlt egy `REGISTERS: list[RegisterDef]` és egy `DEFAULT_UNIT: int`
   definícióval. A pontos firmware-verziószámot használd
   könyvtárnévként — ez az, amivel a `Profile.firmware` és a
   `--firmware` is összevet, slugify/kis-nagybetű átalakítás nélkül.
2. Hozd létre az
   `invforge/profiles/<gyártó>/firmwares/<firmware>/__init__.py`
   fájlt, amely exportál egy modulszintű `PROFILE: Profile`-t (lásd
   `invforge/profiles/sigenergy/firmwares/V100R001C21SPC116/__init__.py`).
3. Add hozzá az `invforge/profiles/<gyártó>/__init__.py`-t, amely
   exportál egy `FIRMWARES: dict[str, Profile]`-t (lásd
   `invforge/profiles/sigenergy/__init__.py`), és regisztráld az
   `invforge/profiles/__init__.py` `_load()` függvényében.
4. Adj hozzá `scenarios/recorded/` (valódi felvételek, alapigazság —
   mindent, amit ezzel a profillal tesztelsz, ezekhez validálj, mielőtt
   egy szintetikus forgatókönyvben megbíznál) és/vagy
   `scenarios/synthetic/` (kitalált rámpák, szélsőértékek, hibás
   adatok — lásd lentebb) YAML-fájlokat az
   `invforge/profiles/<gyártó>/firmwares/<firmware>/scenarios/` alatt.
   Mivel a nyers regiszter-címek firmware-specifikusak, a
   forgatókönyvek ahhoz a firmware-hez tartoznak, amelyhez rögzítették/
   írták őket, nem oszlanak meg lazán egy gyártó firmware-verziói
   között — egy eltérő címzésű második firmware nem értelmezhet
   csendben félre egy régi forgatókönyv-fájlt.
5. Egy meglévő gyártóhoz tartozó második megerősített firmware csak egy
   új testvérkönyvtár a gyártó `firmwares/` mappájában, semmi más nem
   változik.

## Forgatókönyv YAML formátum

```yaml
static:
  unit_<n>: { <cím>: <nyers egész szám|szó-lista|szöveg>, ... }
timeseries:
  - t: <másodperc>
    <cím>: <nyers egész szám|szó-lista>   # egy regiszter kihagyása egy
    ...                                     # mintánál azt jelenti, hogy
                                             # "itt nincs mintavétel", nem
                                             # azt, hogy "nulla" -- az
                                             # előző érték érvényben marad.
                                             # A profil default_unit-jára
                                             # vonatkozik.
exceptions:
  unit_<n>: { <cím>: {function_code: <n>, exception_code: <n>} }
offline:
  - { start: <másodperc>, end: <másodperc> }   # a Modbus TCP nem
    ...                                          # elérhető minden egyes
                                                   # [start, end)
                                                   # ablakban, a
                                                   # forgatókönyv eltelt
                                                   # ideje szerint.
```

Minden numerikus érték NYERS huzalérték (szorzás/gain előtti), sosem a
dekódolt, valós világbeli érték — egyszerű egész szám egyregiszteres
mezőknél, `[hi, lo]` szó-lista a többregiszteres (S32/U32) mezőknél.

## Paraméteres rámpa-forgatókönyvek

A gyakori lineáris rámpákhoz egy `linear-<drain|charge>-<start>-to-<end>-<duration>s`
mintának megfelelő forgatókönyv-név (pl. `linear-drain-100-to-0-60s`)
menet közben kiszámításra kerül, ahelyett hogy minden pontos numerikus
variánshoz kézzel írt YAML-fájlra lenne szükség — lásd
`invforge/core/generator.py`. Ez tisztán kiegészíti a YAML-könyvtárat: egy
már létező, azonos nevű fixture ütközés esetén mindig előnyt élvez.
Megköveteli, hogy a profil megadjon egy `ramp_builder`-t (lásd
`invforge/profiles/sigenergy/firmwares/V100R001C21SPC116/ramps.py`-t mint
referenciapéldát — ez a névleges kapacitásból és a kért töltöttség-
változásból/időtartamból vezeti le a rámpa teljesítményét, nem egy
találgatott konstansból). Az érvénytelen rámpák (nem pozitív időtartam,
egy `drain`, amely nem csökken, egy `charge`, amely nem nő) `ValueError`-
ral utasításra kerülnek (`POST /scenario` → HTTP 400).

## Offline / kapcsolatmegszakítás szimuláció

Egy forgatókönyv `offline:` szekciója (lásd fentebb), vagy egy igény
szerinti `POST /fault` hívás valóban elérhetetlenné teszi a Modbus TCP
figyelőt egy ablak erejéig — egy valódi, megszakadt/elutasított
kapcsolat, nem egy Modbus-szintű kivétel — szimulálva, hogy egy eszköz
ténylegesen offline állapotba kerül (áramkimaradás, hálózati kiesés,
Modbus-támogatás visszavonása). Lásd az `invforge/core/connectivity.py`
modul-docstringjét arról, hogyan van ez megvalósítva a pymodbus felett
(közvetlenül egy `ModbusTcpServer` felépítésével, saját asyncio
eseményhurokban, mivel a blokkoló `StartTcpServer` kényelmi wrapper nem
állítható le/indítható újra kívülről, ha egyszer fut), és arról, hogy
más Modbus kivétel-kódok (`SlaveBusy`, `GatewayNoResponse`, stb.) miért
nem érhetők el a pymodbus adattár `validate()` útvonalán keresztül úgy,
ahogy az `IllegalAddress`.

## Hibás adatot tartalmazó forgatókönyvek

A `scenarios/synthetic/` fixture-ök egy olyan kategóriája, amely nulla új
motor-mechanizmust igényel — csupán egy szándékosan a specifikáción
kívüli `static:` értéket, mivel a motor egyébként is bármilyen nyers
értéket kiír, amit egy YAML megad neki. Ezek arra valók, hogy teszteljék,
egy driver validálja-e az adatot ahelyett, hogy vakon megbízna benne:
huzalszinten érvényes regiszterkódolások is dekódolhatnak fizikailag/
szemantikailag lehetetlen értékekre (egy valódi firmware-hiba vagy egy
sérült olvasás pontosan ezt adhatja egy drivernek). Lásd:
`invforge/profiles/sigenergy/firmwares/V100R001C21SPC116/scenarios/synthetic/`:

- `bad-data-soc-over-100.yaml` — a `battery.charge`-nak megfelelő
  regiszter 101.0%-ra dekódol.
- `bad-data-soh-over-100.yaml` — az állapot-egészség (SoH) regiszter
  150.0%-ra dekódol.
- `bad-data-pv-power-negative.yaml` — egy csak-nagyságrendi
  (termelési) teljesítmény-regiszter negatívra dekódol. A kétirányú
  töltés/kisütés vagy import/export teljesítmény-regiszterek helyett ezt
  választottuk, mivel azoknál a negatív érték eleve, tervezésből
  jelentéssel bír.

## Docker

```bash
docker compose up -d --build
curl http://127.0.0.1:8080/health
```

A modbus `5020:502` és a vezérlő-API `8080:8080` portjait térképezi fel
(megegyezik a fenti Gyorsindítással). Az image `ENTRYPOINT`-ja
`python -m invforge`, egy `CMD`-vel, amely ésszerű alapértékeket ad
(`--vendor sigenergy --firmware V100R001C21SPC116 ...`); a gyártó/
firmware/forgatókönyv felülírható a "paraméterezés Dockeren keresztül"
mintával:

```bash
docker run <image> --vendor sigenergy --firmware V100R001C21SPC116 --scenario ramp-discharge-100-to-0
```

vagy egy `command:` felülírással a `docker-compose.yml`-ben. A
`GET /health` szolgál a konténer `HEALTHCHECK`-jének alapjául.

## Tesztelés

- `tests/unit/` — gyors, hálózat nélküli: `pytest tests/unit -q`.
- `tests/integration/` — valódi Modbus TCP + HTTP egy futó példány ellen.
  Egyparancsos helyi futtatás (build, healthy-re várás, futtatás,
  leállítás): `scripts/integration-test.sh`. CI-ban
  (`.github/workflows/ci.yml`) ugyanezek a lépések két jobként futnak
  (`unit`, `integration`), így egy lint/type/unit hiba gyorsan elbukik,
  mielőtt a Docker egyáltalán buildelne.
- Minden, ebbe a repóba történő push-nak át kell mennie az
  `invforge-review` skillen (`.claude/skills/invforge-review/`) —
  lásd `CLAUDE.md`.

## Licenc

MIT (`LICENSE`) — ez teszt-eszköz, nem eladásra szánt termék; nincs
ok a felhasználás korlátozására.
