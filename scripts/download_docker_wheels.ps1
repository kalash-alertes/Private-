# Télécharge (depuis Windows) les paquets Linux / Python 3.12 de requirements.txt dans docker_wheels/,
# pour construire l'image Docker sans accès Internet depuis WSL. Réessaie jusqu'à 5 fois (connexion instable vers PyPI).
# `uvloop` est ajouté à part : dépendance de uvicorn[standard] réservée à Linux, que pip ignore quand il tourne sous Windows.
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot
for ($attempt = 1; $attempt -le 5; $attempt++) {
    python -m pip download --retries 10 --timeout 180 -r requirements.txt `
        "uvloop>=0.15.1" -d docker_wheels --only-binary=:all: `
        --implementation cp --python-version 3.12 --abi cp312 --abi abi3 --abi none `
        --platform manylinux2014_x86_64 --platform manylinux_2_17_x86_64 --platform manylinux_2_28_x86_64 `
        --platform manylinux_2_34_x86_64 --platform linux_x86_64 --platform any
    if ($LASTEXITCODE -eq 0) { Write-Host "Paquets prêts dans docker_wheels/." ; exit 0 }
    Write-Host "Téléchargement interrompu (essai $attempt/5), nouvel essai..."
}
Write-Error "Échec du téléchargement après 5 essais : vérifier la connexion Internet."
exit 1
