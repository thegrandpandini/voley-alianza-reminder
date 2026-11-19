<#
.SYNOPSIS
    Publica este proyecto en GitHub para poder suscribirse al calendario .ics
    desde el iPhone / Mac (GitHub Pages necesita un repo publico).

.DESCRIPTION
    Hace todo el trabajo de git de una sola vez, de forma segura:
      1. Verifica que git exista.
      2. Crea el repositorio local y el primer commit.
      3. Comprueba que NO se este subiendo ninguna credencial.
      4. Conecta con tu repo de GitHub y hace push.

    Antes de correrlo, crea el repositorio VACIO en https://github.com/new
      - Nombre:  voley-alianza-reminder
      - Visibilidad:  Public
      - NO marques "Add a README file" (debe quedar vacio).

.EXAMPLE
    .\publicar_en_github.ps1 -Usuario aldo

.EXAMPLE
    .\publicar_en_github.ps1 -Usuario aldo -Nombre "Aldo W." -Correo "aldo@example.com"
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Usuario,

    [string]$Repo = "voley-alianza-reminder",
    [string]$Nombre = "",
    [string]$Correo = ""
)

# "Continue" a proposito: en Windows PowerShell 5.1 la salida de error de un
# programa externo (git) se convierte en un error terminante si esto es "Stop",
# y git escribe avisos normales por stderr. Cada fallo real se comprueba con
# $LASTEXITCODE.
$ErrorActionPreference = "Continue"
$ProgressPreference = "SilentlyContinue"
Set-Location -LiteralPath $PSScriptRoot

function Paso($texto) { Write-Host "`n> $texto" -ForegroundColor Cyan }
function Ok($texto)   { Write-Host "  [OK] $texto" -ForegroundColor Green }
function Mal($texto)  { Write-Host "  [ERROR] $texto" -ForegroundColor Red }
function Aviso($texto){ Write-Host "  [!] $texto" -ForegroundColor DarkYellow }

function Get-PythonExe {
    foreach ($candidato in @("python", "py", "python3")) {
        $cmd = Get-Command $candidato -ErrorAction SilentlyContinue
        if ($cmd) { return $cmd.Source }
    }
    return $null
}

# --- 1. git disponible -------------------------------------------------------
Paso "Comprobando git"
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    $posible = "C:\Program Files\Git\cmd\git.exe"
    if (Test-Path $posible) {
        $env:Path += ";C:\Program Files\Git\cmd"
        Ok "git encontrado (agregado al PATH de esta sesion)"
    } else {
        Mal "No encuentro git. Instalalo con:  winget install --id Git.Git -e --source winget"
        exit 1
    }
}
Ok (& git --version)

# --- 2. repositorio local (va ANTES de la identidad) -------------------------
if (-not (Test-Path ".git")) {
    Paso "Creando el repositorio local"
    git init 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) { Mal "git init fallo"; exit 1 }
    git branch -M main 2>&1 | Out-Null
    Ok "Repositorio creado (rama main)"
}

# --- 3. identidad (solo este repositorio, no global) -------------------------
Paso "Identidad de los commits"
if (-not (git config --local user.name)) {
    if (-not $Nombre) { $Nombre = Read-Host "  Tu nombre (para el autor del commit)" }
    if (-not $Nombre) { Mal "Hace falta un nombre."; exit 1 }
    git config --local user.name $Nombre
}
if (-not (git config --local user.email)) {
    if (-not $Correo) { $Correo = Read-Host "  Tu correo (para el autor del commit)" }
    if (-not $Correo) { Mal "Hace falta un correo."; exit 1 }
    git config --local user.email $Correo
}
Ok "$(git config --local user.name) <$(git config --local user.email)>"

# --- 4. configuracion de git -------------------------------------------------
# Sin esto, git avisa de conversiones LF/CRLF en cada archivo (ruido inutil).
git config core.autocrlf false 2>&1 | Out-Null

# --- 5. resguardo: ninguna credencial debe entrar ----------------------------
Paso "Revisando que no se suba ninguna credencial"
git add -A 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) { Mal "git add fallo"; exit 1 }

# 5a. Por nombre de archivo.
$peligrosos = @(git diff --cached --name-only) | Where-Object {
    $_ -match '(^|/)(client_secret\.json|token\.json)$'
}
if ($peligrosos.Count -gt 0) {
    Mal "Estos archivos son credenciales y estaban por subirse:"
    $peligrosos | ForEach-Object { Write-Host "       $_" }
    git rm --cached --quiet $peligrosos 2>&1 | Out-Null
    Mal "Los quite del indice. Revisa .gitignore antes de seguir."
    exit 1
}

# 5b. Por contenido: valores que parecen secretos reales.
#     Ojo: que el codigo mencione "client_secret" es normal y NO es un secreto.
#     Los patrones van partidos en dos trozos a proposito: si estuvieran
#     escritos completos, este mismo archivo se marcaria a si mismo.
$patClientSecret = 'GOCSPX' + '-[A-Za-z0-9_-]{10,}'          # valor de client_secret
$patRefresh      = '"refresh_' + 'token"\s*:\s*"1//'          # refresh_token real
$patPrivateKey   = 'BEGIN PRIV' + 'ATE KEY'                   # cuenta de servicio

$staged = (git diff --cached --diff-filter=ACM) -join "`n"
if ($staged -match $patClientSecret -or
    $staged -match $patRefresh -or
    $staged -match $patPrivateKey) {
    Mal "El contenido del commit parece incluir un secreto de Google (con valor real)."
    Mal "Revisa lo agregado con:  git diff --cached"
    exit 1
}
Ok "Sin credenciales en el commit"

# --- 6. commit ---------------------------------------------------------------
Paso "Creando el commit"
if (git status --porcelain) {
    $commitOut = git commit -m "Recordatorio automatico de partidos de Alianza Lima Voley" 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host ($commitOut | Out-String) -ForegroundColor DarkGray
        Mal "El commit fallo. El mensaje de arriba dice por que."
        exit 1
    }
    Ok "Commit creado"
} else {
    Ok "No hay cambios nuevos que commitear"
}

# Verificacion real: que exista al menos un commit antes de intentar el push.
git rev-parse --verify HEAD 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Mal "El repositorio no tiene ningun commit; no se puede subir nada."
    exit 1
}

# --- 7. integrar lo que el robot ya subio ------------------------------------
# El workflow hace un commit diario con el .ics actualizado. Si no integramos
# esos commits, GitHub rechaza el push con "fetch first".
Paso "Comprobando si GitHub tiene commits nuevos"
git fetch origin 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Aviso "No pude consultar GitHub (sin red o sin sesion). Sigo igual."
} else {
    git rev-parse --verify --quiet origin/main 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) {
        $behind = [int](git rev-list --count HEAD..origin/main 2>&1)
        if ($behind -gt 0) {
            Write-Host "  Hay $behind commit(s) en GitHub que no tienes (los crea el robot)."
            # Usamos merge (no rebase) porque `git commit --no-edit` cierra el merge
            # sin abrir editor, cosa que un rebase si exige.
            git merge --no-edit origin/main 2>&1 | Out-Null
            if ($LASTEXITCODE -ne 0) {
                Write-Host "  Conflicto en archivos generados; regenero el calendario."
                $python = Get-PythonExe
                if ($python) { & $python "sync.py" ics 2>&1 | Out-Null }
                git add "docs/alianza-lima.ics" 2>&1 | Out-Null
                git commit --no-edit 2>&1 | Out-Null
                if ($LASTEXITCODE -ne 0) {
                    Mal "No logre cerrar la integracion de los cambios de GitHub."
                    Mal "Arreglo manual:  git merge --abort  y luego  git pull origin main"
                    exit 1
                }
            }
            Ok "Integrados los cambios de GitHub"
        } else {
            Ok "Ya estabas al dia"
        }
    }
}

# --- 8. remoto ---------------------------------------------------------------
$remoto = "https://github.com/$Usuario/$Repo.git"
Paso "Conectando con $remoto"
if (@(git remote) -contains "origin") {
    git remote set-url origin $remoto
} else {
    git remote add origin $remoto
}

# --- 9. push -----------------------------------------------------------------
Paso "Subiendo a GitHub (puede abrirse una ventana para iniciar sesion)"
$pushOut = git push -u origin main 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host ($pushOut | Out-String) -ForegroundColor DarkGray
    if ($pushOut -match 'fetch first|non-fast-forward') {
        Mal "GitHub tiene commits que no estan en tu copia."
        Mal "Vuelve a correr el script: ya integra esos commits automaticamente."
    } elseif ($pushOut -match 'Authentication failed|could not read Username|SEC_E_NO_CREDENTIALS') {
        Mal "No se pudo autenticar con GitHub. Vuelve a correrlo y completa la ventana de inicio de sesion."
    } else {
        Mal "El push fallo. Causas tipicas:"
        Write-Host "    - Aun no creaste el repositorio en https://github.com/new (publico y vacio)."
        Write-Host "    - El usuario '$Usuario' o el repo '$Repo' estan mal escritos."
        Write-Host "    - Se abrio una ventana de inicio de sesion: completala y reintenta."
    }
    exit 1
}

# --- 9. resultado ------------------------------------------------------------
$urlPages = "https://$($Usuario.ToLower()).github.io/$Repo/alianza-lima.ics"
Write-Host ""
Write-Host ("=" * 72) -ForegroundColor Green
Write-Host " Subido. Faltan dos pasos en GitHub y uno en tu iPhone/Mac" -ForegroundColor Green
Write-Host ("=" * 72) -ForegroundColor Green
Write-Host @"

 1) Activar GitHub Pages
    https://github.com/$Usuario/$Repo/settings/pages
    Source:  Deploy from a branch
    Branch:  main     Carpeta:  /docs      ->  Save

    En 1-2 minutos comprueba que descarga:
    $urlPages

 2) Que se actualice solo cada dia
    Pestana "Actions" -> habilitar workflows -> "Run workflow"

 3) Suscribirte (DESMARCA "Eliminar avisos")
    Mac:     Calendario -> Archivo -> Nueva suscripcion de calendario
    iPhone:  Ajustes -> Apps -> Calendario -> Cuentas de calendario
             -> Anadir cuenta -> Otro -> Anadir calendario suscrito

"@
