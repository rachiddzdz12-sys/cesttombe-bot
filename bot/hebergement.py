"""Met les images en ligne sur un dépôt GitHub PUBLIC pour qu'Instagram puisse les télécharger.

Chaque envoi remplace tout le contenu du dépôt (historique effacé) : il ne grossit jamais.
"""
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

import requests


class ErreurHebergement(Exception):
    pass


def _git(args, cwd, secret=""):
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    if r.returncode != 0:
        msg = (r.stderr or r.stdout).replace(secret, "***") if secret else (r.stderr or r.stdout)
        raise ErreurHebergement(f"git {args[0]} : {msg.strip()[:300]}")


def heberger(fichiers):
    repo, token = os.environ.get("IMAGES_REPO"), os.environ.get("IMAGES_TOKEN")
    if not repo or not token:
        raise ErreurHebergement("IMAGES_REPO ou IMAGES_TOKEN manquant")
    tmp = Path(tempfile.mkdtemp())
    try:
        (tmp / "p").mkdir()
        for f in fichiers:
            shutil.copy(f, tmp / "p" / Path(f).name)
        _git(["init", "-q", "-b", "main"], tmp)
        _git(["config", "user.name", "cesttombe-bot"], tmp)
        _git(["config", "user.email", "cesttombe-bot@users.noreply.github.com"], tmp)
        _git(["add", "-A"], tmp)
        _git(["commit", "-q", "-m", "images du post"], tmp)
        _git(["push", "-q", "--force", f"https://bot:{token}@github.com/{repo}.git", "main"], tmp, secret=token)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    urls = [f"https://raw.githubusercontent.com/{repo}/main/p/{Path(f).name}" for f in fichiers]
    for u in urls:                      # on attend que chaque image soit vraiment en ligne
        for _ in range(12):
            try:
                if requests.head(u, timeout=15).status_code == 200:
                    break
            except requests.RequestException:
                pass
            time.sleep(5)
        else:
            raise ErreurHebergement(f"image pas accessible publiquement : {u}")
    return urls
