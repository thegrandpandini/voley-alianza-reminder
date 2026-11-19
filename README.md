# 🏐 Alianza Lima Vóley — recordatorio automático de partidos

Te avisa en tu calendario cuando juega **Club Alianza Lima** en la Liga Nacional
Superior de Voleibol del Perú **y en cualquier otra competencia** (Sudamericano de
Clubes, amistosos). Sin apps nuevas, sin pagar nada, y sin revisar la web de la FPV
a mano.

```
                 ┌─────────────────┐
   cada mañana   │  GitHub Actions │  (gratis, en la nube, tu PC apagada)
                 └────────┬────────┘
                          │ lee
                 ┌────────▼────────┐
                 │  API de la FPV  │  fpv.org.pe  (datos oficiales)
                 └────────┬────────┘
                          │ filtra por ID de equipo = 138
                 ┌────────▼────────┐
                 │  Tu calendario  │  partidos + avisos 1 día y 1 hora antes
                 └─────────────────┘
```

---

## Lo bueno: los datos ya están estructurados

La web de la FPV **no hay que hacerle scrapping**. Por dentro es WordPress con el
plugin *SportsPress*, que publica una API JSON pública:

```
https://fpv.org.pe/wp-json/sportspress/v2/events
```

Eso nos da fecha, hora, equipos, sede y duración como datos limpios. Es mucho más
estable que leer HTML, que se rompe cada vez que rediseñan la página.

### Tres cosas que descubrimos probando la API (y que este código respeta)

| Descubrimiento | Consecuencia |
|---|---|
| El parámetro `?teams=` **se ignora en silencio** | Pedir `?teams=138` devuelve *todos* los partidos. El filtro se hace en el código, y hay un test que lo vigila. |
| `?leagues=`, `?after=` **sí** funcionan | Los usamos para bajar solo lo necesario: ~12 eventos en vez de los 388 de la temporada completa. |
| "Club Alianza Lima" es **ID 138**; "Deportivo Alianza" es **ID 1774** | Son equipos distintos. Filtrar por nombre (`"alianza" in nombre`) habría metido partidos del equipo equivocado. Filtramos por **ID**. |

Otro detalle: la FPV guarda horas con segundos basura (`18:30:46` para un partido de
las 18:30). El código los descarta antes de agendar.

---

## Lo que necesitas

- **Windows, macOS o Linux** con **Python 3.10 o más nuevo**.
  En este equipo ya está: Python 3.12.
- Para la automatización: una cuenta de GitHub (gratis). **Git ya está instalado**
  en este equipo (paso A1).
- **Ninguna librería que instalar.** El proyecto usa solo la librería estándar de
  Python. Nada de `pip install`, nada de entornos virtuales.

---

## Probarlo ahora mismo (sin configurar nada)

Abre una terminal en esta carpeta:

```powershell
python sync.py check
```

Deberías ver algo así:

```
🔎 Consultando la FPV para Alianza Lima (equipo ID 138)...

✅ 2 partido(s) por jugar:

  Sun 22/11/2026 18:30  🏐 Alianza Lima vs Atlético Atenea · LNSV
   📍 Polideportivo Luisa Fuentes
  Sat 28/11/2026 17:00  🏐 Alianza Lima vs Perú U-19 · LNSV
   📍 Polideportivo Luisa Fuentes
```

Las horas salen en **hora del Este** (configurable, ver `VOLEY_DISPLAY_TZ`).

Si ves eso, **la parte difícil ya está resuelta**. Ahora elige el camino.

---

## ¿Qué camino me conviene?

| | **Apple Calendar** | **Google Calendar (API)** |
|---|---|---|
| Dificultad | Media | Media-alta |
| Necesitas | Un Mac/iPhone/iPad + repo **público** en GitHub | Proyecto en Google Cloud + autorización |
| Avisos "1 día / 1 hora antes" | ✅ Sí, vienen en el `.ics` | ✅ Sí, y los controlas con `VOLEY_REMINDERS` |
| Se actualiza solo | ✅ Cada día (suscripción) | ✅ Cada día |
| Editar/detener avisos por evento | No (es de solo lectura) | Sí |
| Si cambia la hora de un partido | Se actualiza al refrescar | Se actualiza al correr el robot |
| Qué tan rápido llega el cambio | Según el intervalo de refresco (15 min–1 h) | Al día siguiente |

> **Ojo con Windows:** no existe "Apple Calendar" para Windows. Si no tienes ningún
> equipo Apple (Mac, iPhone o iPad), usa el camino de Google Calendar.

---

# Camino A — Apple Calendar (suscripción al `.ics`)

La idea: GitHub genera el `.ics` cada mañana y lo publica en una URL fija. Tu
iPhone o Mac se suscribe a esa URL y se actualiza solo.

**Lo único especial que se necesita: una URL pública.** La conseguimos gratis con
GitHub Pages.

### Paso A1 · Comprobar Git

**Git ya está instalado en este equipo** (`C:\Program Files\Git\cmd`, versión 2.56).
Abre una terminal nueva y comprueba:

```powershell
git --version
```

Si tu terminal aún no lo reconoce, ciérrala y ábrela otra vez (el PATH se
actualiza al iniciar sesión).

### Paso A2 · Crear el repositorio en GitHub

1. Entra a <https://github.com/new>.
2. Nombre: `voley-alianza-reminder`.
3. Visibilidad: **Public** (obligatorio para GitHub Pages gratis).
4. **No** marques *"Add a README file"* — el repo debe quedar vacío.
5. **Create repository**.

### Paso A3 · Publicar con un solo comando

En la carpeta del proyecto:

```powershell
.\publicar_en_github.ps1 -Usuario TU-USUARIO-DE-GITHUB
```

El script se encarga de todo: crea el repositorio local, comprueba que **no se
suba ninguna credencial**, hace el primer commit y lo sube a GitHub.

Si Windows bloquea la ejecución de scripts (`... no se puede cargar
porque la ejecución de scripts está deshabilitada`), usa esta variante:

```powershell
powershell -ExecutionPolicy Bypass -File .\publicar_en_github.ps1 -Usuario TU-USUARIO
```

> **¿Por qué el repo tiene que ser público?** GitHub Pages lo exige en el plan
> gratuito ([documentación](https://docs.github.com/en/pages/getting-started-with-github-pages/creating-a-github-pages-site)).
> No pasa nada: lo que se publica es el código y el calendario de partidos.
> **Nunca** se suben credenciales: están en `.gitignore` y el script se niega a
> hacer el commit si detecta un `token.json`, un `client_secret.json` o un valor
> con pinta de secreto de Google.
>
> Si prefieres repo privado: usa Netlify o Cloudflare Pages (también gratis y
> admiten repos privados) apuntando a la carpeta `docs/`.

### Paso A4 · Activar GitHub Pages

En tu repo: **Settings** → **Pages** →
*Source*: **Deploy from a branch** → *Branch*: **`main`**, carpeta **`/docs`** → **Save**.

En 1–2 minutos tu calendario estará en:

```
https://TU-USUARIO.github.io/voley-alianza-reminder/alianza-lima.ics
```

Ábrela en el navegador para comprobar que descarga el archivo.

### Paso A5 · Automatizar la actualización

Ya tienes el repositorio; sólo falta que el robot escriba el `.ics` cada día.

1. Pestaña **Actions** → habilita los workflows si te lo pregunta.
2. Elige **Sincronizar partidos de Alianza Lima** → **Run workflow** → **Run**.
3. Debe salir en verde ✅.

**No necesitas configurar ningún secreto para este camino.** El paso de Google se
salta solo si no existe el secreto.

Desde ahora corre a diario a las **07:00 (hora de Lima)** y hace commit del `.ics`
actualizado. GitHub Pages lo publica en un minuto.

### Paso A6 · Suscribirte en el Mac

1. Abre **Calendario**.
2. Menú **Archivo → Nueva suscripción de calendario**.
3. Pega la URL (`https://TU-USUARIO.github.io/.../alianza-lima.ics`) → **Suscribirse**.
4. ⚠️ En la ventana de opciones:
   - **Desmarca "Eliminar avisos"** (Remove Alarms). Si queda marcado, Apple
     borra los avisos del archivo y **no te sonará nada**.
   - **Actualizar**: cada hora (o cada 15 minutos).
   - **Ubicación**: tu cuenta iCloud, si quieres verlo también en el iPhone.
5. **OK**.

### Paso A7 · Suscribirte en el iPhone / iPad

1. **Ajustes → Apps → Calendario → Cuentas de calendario → Añadir cuenta →
   Otro → Añadir calendario suscrito**.
   (En versiones anteriores: *Ajustes → Calendario → Cuentas*.)
2. Pega la URL en **Servidor** → **Siguiente** → **Guardar**.
3. ⚠️ En esa misma pantalla, **desactiva "Eliminar avisos"**. Viene activado por
   defecto y es la razón #1 por la que "no suena nada".
4. Listo: los partidos aparecen en tu Calendario, con aviso **1 día antes** y
   **1 hora antes**.

> Atajo: cambia `https://` por `webcal://` y abre el enlace desde el dispositivo;
> suele ofrecer la suscripción directamente.

---

# Camino B — Google Calendar con avisos nativos

Si tu día a día está en Google Calendar (Android, escritorio), este es el camino.
Los eventos se **crean** en tu calendario: puedes editarlos, moverlos o cambiar los
avisos, y no se duplican al correr el robot varias veces.

### Paso B1 · Crear el proyecto en Google Cloud

1. Entra a <https://console.cloud.google.com/> con tu cuenta.
2. Arriba, selector de proyecto → **New Project** → nombre `voley-alianza` →
   **Create**. Asegúrate de estar dentro de él.

### Paso B2 · Activar la API del calendario

**APIs & Services** → **Library** → busca **Google Calendar API** → **Enable**.

### Paso B3 · Pantalla de consentimiento

1. **APIs & Services** → **OAuth consent screen**.
2. Tipo **External** → **Create**.
3. *App name*: `voley-alianza`; tu correo en *User support email* y *Developer
   contact* → **Save and Continue**.
4. **Scopes**: no agregues nada → **Save and Continue**.
5. **Test users**: agrega tu propia cuenta → **Save and Continue**.
6. ⚠️ **Muy importante** — vuelve a **OAuth consent screen** y pulsa
   **Publish app** (pasar de *Testing* a *In production*).

   > Con la app en *Testing*, Google caduca el `refresh_token` **a los 7 días** y la
   > automatización se rompe cada semana sin decir por qué. Publicándola —aunque
   > quede "sin verificar", que es normal para uso personal— el token dura
   > indefinidamente. No hace falta revisión de Google.

### Paso B4 · Descargar las credenciales

**Credentials** → **+ Create Credentials** → **OAuth client ID** →
*Application type*: **Desktop app** → **Create** → **Download JSON**.

Renombra el archivo a `client_secret.json` y déjalo en esta carpeta.

> 🔒 Es una credencial: ya está en `.gitignore`, y `publicar_en_github.ps1` se
> niega a subirla si detecta que quedó dentro del commit.

### Paso B5 · Autorizar (una sola vez)

```powershell
python sync.py login
```

Se abre el navegador → elige tu cuenta → *"Google no ha verificado esta
aplicación"* → **Advanced** → **Go to voley-alianza (unsafe)** (es normal: la app
es tuya) → acepta el permiso de calendario.

### Paso B6 · Probar y luego aplicar

```powershell
python sync.py sync --dry-run    # simula, no escribe nada
python sync.py sync              # escribe en tu calendario
```

Abre <https://calendar.google.com>: ahí están los partidos con avisos **1 día** y
**1 hora** antes. Si vuelves a correr `sync`, debe decir *"Sin cambios"* — si dice
"Creados" otra vez, hay un bug, avísame.

### Paso B7 · Que corra solo en GitHub

1. Abre `token.json` en el Bloc de notas y copia **todo** el contenido.
2. En el repo: **Settings → Secrets and variables → Actions → New repository
   secret**. Nombre: `VOLEY_TOKEN_JSON`. Valor: lo copiado.
3. **Actions → Run workflow** para probar.

> El repo puede ser privado en este camino (no usas Pages). Pero si ya seguiste el
> Camino A, con dejarlo público todo funciona igual.

---

# Camino C — Sin cuentas, importando a mano

Sólo si quieres lo mínimo:

```powershell
python sync.py ics
```

Genera `docs/alianza-lima.ics`. Ábrelo y los eventos se agregan a tu calendario
con sus avisos.

- **Apple / Outlook**: funcionan los avisos del archivo.
- **Google Calendar**: *Configuración → Importar y exportar → Importar*. Es una
  **foto del momento**: cuando la FPV publique más partidos, tendrás que repetirlo.

Sin suscripción no hay actualización automática.

---

## Configuración

Variables de entorno (o edita `voley/config.py`):

| Variable | Default | Qué hace |
|---|---|---|
| `VOLEY_REMINDERS` | `1440,60` | Minutos antes para cada aviso. `1440` = 1 día, `60` = 1 hora. Ej: `2880,120,30` |
| `VOLEY_TEAM_ID` | `138` | Qué equipo seguir |
| `VOLEY_LEAGUE_ID` | `0` | `0` = **todas las competencias** (LNSV + Sudamericano + amistosos). `10` = sólo LNSV |
| `VOLEY_CALENDAR_ID` | `primary` | Otro calendario (sólo Camino B) |
| `VOLEY_TRANSPARENCY` | `transparent` | `opaque` para que el partido bloquee la agenda |
| `VOLEY_LOOKAHEAD_DAYS` | `400` | Cuántos días hacia adelante revisar |
| `VOLEY_DISPLAY_TZ` | `America/New_York` | Zona en que se escriben las horas legibles: `America/New_York`, `America/Lima` o `UTC` |

```powershell
$env:VOLEY_REMINDERS = "1440,120,30"; python sync.py ics
```

> En GitHub Actions, para cambiar la configuración sin tocar el código: agrega esas
> variables como *Variables* del repo (Settings → Secrets and variables → Actions →
> **Variables**) y el workflow las heredará. O edita `voley/config.py` directamente.

### Cómo se manejan las horas (importante)

Los eventos **se guardan en UTC**, que es una hora absoluta. Eso significa que cada
dispositivo los muestra en *su* hora local automáticamente: si abres el calendario
en Nueva York sale en hora del Este, y si lo abres en Lima sale en hora de Lima.
La hora del partido no cambia, sólo la forma de mostrarla.

`VOLEY_DISPLAY_TZ` sólo decide **el texto** dentro de la descripción del evento (y
la salida de `python sync.py check`). Por defecto es hora del Este.

Ojo con un detalle que confunde: **Lima es UTC-5 todo el año**, pero Nueva York
cambia de hora dos veces al año:

| Época | Nueva York | Diferencia |
|---|---|---|
| Nov–Mar (invierno) | EST, UTC-5 | Idéntica a Lima |
| Mar–Nov (verano) | EDT, UTC-4 | Los partidos se ven **1 hora más tarde** |

Por eso, en pleno verano, un partido de las 18:30 en Lima se ve a las **19:30** del
Este. La descripción del evento lo aclara mostrando ambas horas:

```
Inicio: 15/07/2026 19:30 (hora del Este) · 18:30 en Lima
```

Y cuando coinciden, no repite la misma hora para no ensuciar el evento. Esta regla
se aplica a mano porque Windows no trae base de datos de zonas horarias
(`zoneinfo` falla); está cubierta con 16 tests, incluidos los dos cambios de hora.

### Cambiar de equipo

```powershell
python -c "from voley import fpv; [print(i, n) for i, n in sorted(fpv.fetch_teams().items())]"
```

Copia el ID y úsalo con `VOLEY_TEAM_ID`.

---

## Problemas frecuentes

**En Apple no suena ningún aviso**
Casi siempre es *"Eliminar avisos"* activado en la suscripción. En Mac:
selecciona el calendario en la barra lateral → **Editar → Obtener información** y
desmarca esa casilla. En iPhone: *Ajustes → Apps → Calendario → Cuentas de
calendario → [tu suscripción]* → desactiva *Eliminar avisos*.

**La URL de Pages da 404**
Pages tarda 1–2 minutos tras activarlo. Revisa que la *Source* sea
`main` + `/docs`. La URL exacta aparece en Settings → Pages.

**El `.ics` no cambia nunca**
Mira la pestaña **Actions**: si el workflow falló, ejecuta *Run workflow*. GitHub
desactiva los workflows programados tras **60 días sin actividad** en el repo; si
te llega ese correo, entra a Actions y pulsa *Enable workflow*.

**`No encontré client_secret.json`** (Camino B)
El paso B4 quedó a medias: descarga el JSON del cliente OAuth tipo *Desktop app*.

**`Google no devolvió refresh_token`**
Ya habías autorizado antes. Quita el acceso en
<https://myaccount.google.com/permissions> y repite `python sync.py login`.

**Dejó de funcionar a la semana** (sólo Camino B)
Es el modo *Testing*: publica la app (paso B3.6), repite `login` y actualiza el
secreto `VOLEY_TOKEN_JSON`.

**No aparecen partidos nuevos**
Puede que la FPV aún no los publique (suelen cargarse con pocos días de
anticipación). El robot corre a diario, así que los captura en cuanto salgan.

---

## Tests

```powershell
python -m unittest discover -s tests -t . -v
```

46 pruebas: que el filtro por ID rechace a *Deportivo Alianza*, que los segundos
basura se descarten, que los avisos del `.ics` sean válidos, la conversión a UTC,
el escapado y plegado de líneas, que no dependamos de `?teams=`, y las reglas de
horario de verano del Este (incluidos los dos cambios de hora).

Los fixtures son respuestas reales de la API. Para refrescarlos:

```powershell
python tests/capture_fixture.py
```

---

## Estructura

```
voley/
  config.py    Configuración (IDs, avisos, zonas horarias)
  fpv.py       Cliente de la API de la FPV (paginación, reintentos)
  match.py     Modelo del partido + filtro por ID de equipo
  service.py   Une lo anterior en "qué partidos vienen"
  tz.py        Hora del Este / Perú sin depender de tzdata
  ics.py       Generador de archivos .ics (RFC 5545)
  auth.py      Login OAuth con Google (sólo librería estándar)
  gcal.py      Cliente REST de Google Calendar
sync.py        CLI: check / ics / login / sync
publicar_en_github.ps1   Publica el repo en GitHub (con revisión de credenciales)
tests/         46 pruebas + fixtures reales
.github/       Workflow diario
docs/          El .ics publicado (GitHub Pages)
```

---

## Limitaciones que conviene saber

1. **Depende de la FPV.** Si cambian el plugin o cierran la API, hay que adaptar
   `fpv.py`. Los tests con fixtures reales avisan del cambio de formato.
2. **La FPV publica tarde.** A veces carga los partidos con pocos días de
   anticipación; el robot corre a diario, así que los captura en cuanto salgan.
3. **Un solo equipo.** Para seguir dos, corre dos copias con distinto
   `VOLEY_TEAM_ID` y distinto calendario.
4. **Suscripción = sólo lectura.** Con el Camino A no puedes editar un partido ni
   ponerle notas; con el Camino B sí.
5. **Credenciales.** `token.json` y `client_secret.json` viven en esta carpeta (que
   está en Nextcloud). Mantenla privada; si algún día la compartes, revoca el
   acceso en <https://myaccount.google.com/permissions>.

---

Hecho para no volver a perderse un partido de Alianza. 💙🤍
