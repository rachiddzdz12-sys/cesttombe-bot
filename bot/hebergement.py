"""Met les images en ligne pour qu'Instagram puisse les télécharger.

Par défaut, elles vont dans la branche « images » de ce même dépôt (qui doit être PUBLIC),
avec le jeton automatique de GitHub Actions : aucun réglage à faire.
Chaque envoi remplace tout le contenu de la branche (historique effacé) : elle ne grossit jamais.

Option : IMAGES_REPO + IMAGES_TOKEN pour utiliser un autre dépôt public.
"""
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

import requests

BRANCHE = "images"


class ErreurHebergement(Exception):
    pass


def _git(args, cwd, secret=""):
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    if r.returncode != 0:
        msg = r.stderr or r.stdout
        if secret:
            msg = msg.replace(secret, "***")
        raise ErreurHebergement(f"git {args[0]} : {msg.strip()[:300]}")


def cible():
    """(dépôt, jeton) utilisés pour héberger les images."""
    repo = os.environ.get("IMAGES_REPO") or os.environ.get("GITHUB_REPOSITORY")
    token = os.environ.get("IMAGES_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not repo or not token:
        raise ErreurHebergement("dépôt ou jeton manquant pour héberger les images")
    return repo, token


def heberger(fichiers):
    repo, token = cible()
    tmp = Path(tempfile.mkdtemp())
    try:
        (tmp / "p").mkdir()
        for f in fichiers:
            shutil.copy(f, tmp / "p" / Path(f).name)
        (tmp / "README.md").write_text("Images temporaires des posts C'EST TOMBÉ (remplacées à chaque post).\n")
        _git(["init", "-q", "-b", BRANCHE], tmp)
        _git(["config", "user.name", "cesttombe-bot"], tmp)
        _git(["config", "user.email", "cesttombe-bot@users.noreply.github.com"], tmp)
        _git(["add", "-A"], tmp)
        _git(["commit", "-q", "-m", "images du post"], tmp)
        _git(["push", "-q", "--force", f"https://x-access-token:{token}@github.com/{repo}.git",
              f"{BRANCHE}:{BRANCHE}"], tmp, secret=token)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    urls = [f"https://raw.githubusercontent.com/{repo}/{BRANCHE}/p/{Path(f).name}" for f in fichiers]
    for u in urls:                      # on attend que chaque image soit vraiment en ligne
        for _ in range(12):
            try:
                if requests.head(u, timeout=15).status_code == 200:
                    break
            except requests.RequestException:
                pass
            time.sleep(5)
        else:
            raise ErreurHebergement(f"image pas accessible publiquement : {u} (le dépôt est-il public ?)")
    return urls
