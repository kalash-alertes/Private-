# docker_wheels/

Paquets Python **Linux / Python 3.12** utilisés pour construire l'image Docker du backend **sans Internet**.

Pourquoi : depuis Docker sous WSL, les téléchargements depuis PyPI sont lents et se coupent. Windows les télécharge
ici, puis le `Dockerfile` les installe depuis ce dossier.

- Remplir le dossier : `powershell -File scripts\download_docker_wheels.ps1` (à relancer si `requirements.txt` change).
- Dossier vide : le `Dockerfile` installe depuis PyPI, comme avant.
- Les fichiers `.whl` ne sont pas commités (`.gitignore`).
