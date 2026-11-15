"""Reel 9:16 dans la DA « LE BRUIT » (même interface que reel3.fabriquer).
Plans calés sur la voix : accroche (titre), chiffre clé, parties avec sous-titres mot à mot (le mot dit en violet),
question au spectateur, carte de fin (logo B). Les mots sont minutés par la reconnaissance vocale."""
import re
import shutil
import subprocess
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

import config
from bot import bruit_base as bb
from bot import voix
from bot.bruit_base import BLANC, GRIS, VIOLET, VIOLET_TXT, couper, ecrire, largeur, police
from bot.reel import mixer_audio, musique

W, H, FPS, M = 1080, 1920, 30, 84
DELAI = 0.3          # la voix commence 0,3 s après l'image (comme dans reel.mixer_audio)
FIN = 3.2            # durée de la carte de fin
PLAN = 2.4           # durée visée d'un plan


# ------------------------------------------------------------------ mots minutés
def _norm(m):
    m = "".join(c for c in unicodedata.normalize("NFD", (m or "").lower()) if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]", "", m)


def _jetons(liste):
    out = []
    for j in liste:
        if out and not _norm(j["mot"]):
            out[-1] = dict(out[-1], mot=out[-1]["mot"] + ("" if j["mot"].startswith("»") else " ") + j["mot"],
                           fin=j["fin"])
        elif _norm(j["mot"]):
            out.append(dict(j))
    return out


def aligner(texte, reconnus):
    """Le texte exact (affiché) reçoit les instants de la reconnaissance vocale, même quand elle entend mal
    un nom : alignement mot à mot, et répartition régulière sur les passages mal reconnus."""
    vrais = _jetons([{"mot": w, "debut": 0.0, "fin": 0.0} for w in texte.split()])
    rec = _jetons(reconnus)
    if not vrais or not rec:
        return []
    sm = SequenceMatcher(None, [_norm(v["mot"]) for v in vrais], [_norm(r["mot"]) for r in rec], autojunk=False)
    for op, a0, a1, b0, b1 in sm.get_opcodes():
        if op == "equal" or (op == "replace" and a1 - a0 == b1 - b0):
            for i in range(a1 - a0):
                vrais[a0 + i]["debut"], vrais[a0 + i]["fin"] = rec[b0 + i]["debut"], rec[b0 + i]["fin"]
        elif a1 > a0:
            t0 = rec[b0]["debut"] if b0 < len(rec) else rec[-1]["fin"]
            t1 = rec[b1 - 1]["fin"] if b1 > b0 else t0 + 0.25 * (a1 - a0)
            for i in range(a1 - a0):
                vrais[a0 + i]["debut"] = t0 + (t1 - t0) * i / (a1 - a0)
                vrais[a0 + i]["fin"] = t0 + (t1 - t0) * (i + 1) / (a1 - a0)
    return vrais


def mots_minutes(texte, audio, diag):
    """[(mot, début, fin)] en temps du Reel. Reconnaissance vocale si possible, sinon répartition."""
    try:
        modele = voix._asr()
        if modele is not None:
            segs, _ = modele.transcribe(voix._pcm16k(audio), language="fr", word_timestamps=True,
                                        condition_on_previous_text=False)
            rec = [{"mot": w.word.strip(), "debut": w.start, "fin": w.end} for s in segs for w in (s.words or [])]
            mots = aligner(texte, rec)
            if mots:
                return [(m["mot"], m["debut"] + DELAI, m["fin"] + DELAI) for m in mots]
    except Exception as ex:
        diag.append(f"  reel · minutage par reconnaissance vocale impossible : {str(ex)[:80]}")
    from bot import reel3
    return reel3.minuter(texte, audio)


# ------------------------------------------------------------------ plans (photos animées)
class Plan:
    def __init__(self, media, debut, fin, kicker):
        self.debut, self.fin, self.kicker = debut, fin, kicker
        self.mode = bb.mode_photo(media, W, H) if media else "noir"
        self.media = media
        if self.mode == "plein":
            img = bb.look(media["img"])
            cx, cy = bb.centre_sujet(media)
            s = max(W * 1.12 / img.width, H * 1.12 / img.height)
            self.img = img.resize((round(img.width * s) + 1, round(img.height * s) + 1), Image.LANCZOS)
            self.cx, self.cy = cx, cy
            self.ombre = bb._ombre_plein(W, H, True)
        elif self.mode == "haut":
            img = bb.look(media["img"])
            img = img.crop((0, 0, img.width, int(img.height * bb.partie_propre(media))))
            self.h = 1240
            s = max(W * 1.1 / img.width, self.h * 1.1 / img.height)
            self.img = img.resize((round(img.width * s) + 1, round(img.height * s) + 1), Image.LANCZOS)
            self.cx = bb.centre_sujet(media)[0]
            self.masque = bb._masque_haut(W, self.h)[..., None]

    def image(self, t):
        p = bb.ease((t - self.debut) / max(0.1, self.fin - self.debut))
        z = 1.0 + 0.07 * p                       # lent zoom avant
        if self.mode == "plein":
            cw, ch = W * 1.12 / z, H * 1.12 / z
            x0 = min(max(0, self.cx * self.img.width - cw / 2), self.img.width - cw)
            y0 = min(max(0, self.cy * self.img.height - ch * 0.42), self.img.height - ch)
            a = np.asarray(self.img.crop((round(x0), round(y0), round(x0 + cw), round(y0 + ch)))
                           .resize((W, H), Image.BILINEAR)).astype(np.float32) * 0.8
            a *= self.ombre[..., None]
        elif self.mode == "haut":
            cw, ch = W * 1.1 / z, self.h * 1.1 / z
            x0 = min(max(0, self.cx * self.img.width - cw / 2), self.img.width - cw)
            y0 = min(max(0, (self.img.height - ch) * 0.3), self.img.height - ch)
            zone = np.asarray(self.img.crop((round(x0), round(y0), round(x0 + cw), round(y0 + ch)))
                              .resize((W, self.h), Image.BILINEAR)).astype(np.float32) * 0.86
            a = np.empty((H, W, 3), np.float32)
            a[:] = bb.FOND
            y = 110
            a[y:y + self.h] = zone * self.masque + a[y:y + self.h] * (1 - self.masque)
        else:
            return bb.fond_noir(W, H)
        a += GRAINS[int(t * FPS) % len(GRAINS)][..., None]
        return Image.fromarray(a.clip(0, 255).astype(np.uint8)).convert("RGBA")


GRAINS = [np.kron(np.random.default_rng(i).normal(0, 4, (H // 2, W // 2)).astype(np.float32),
                  np.ones((2, 2), np.float32)) for i in range(4)]


# ------------------------------------------------------------------ habillage
F_KICK = police(600, 30)
F_PIED = police(700, 24)
F_ST = police(800, 80)


def nom_page():
    return getattr(config, "NOM_PAGE", "LE BRUIT")


def entete(img, kicker, apparition=1.0):
    d = ImageDraw.Draw(img)
    a = int(255 * apparition)
    x = ecrire(d, M, 128, (kicker or "").upper(), F_KICK, BLANC + (a,), track=3)
    d.line((x + 26, 117, x + 26 + 110 * apparition, 117), fill=VIOLET + (a,), width=3)
    lg = bb.logo(58)
    img.alpha_composite(lg, (W - M - lg.width, 84))


def pied(img, n, total):
    d = ImageDraw.Draw(img)
    ecrire(d, M, 1572, nom_page(), F_PIED, BLANC, track=3)
    txt = f"{n} / {total}"
    ecrire(d, W - M - 120 - largeur(txt, F_PIED, 2), 1572, txt, F_PIED, BLANC, track=2)


def bloc_titre(img, haut, bas, sous, tl, y_bas=1430, taille=118):
    """Titre façon carte « Breaking news » : lignes blanches puis violettes, sous-titre gris, barre violette."""
    lmax = W - 2 * M - 30
    f, lh = bb.ajuster(haut, 800, taille, lmax, 2, mini=72, track_ratio=-0.025)
    lb = couper(bas, f, lmax, track=-int(f.size * 0.025))[:2]
    lignes = [(l, BLANC) for l in lh] + [(l, VIOLET_TXT) for l in lb]
    fs = police(500, 42)
    ls = couper(sous, fs, lmax - 100)[:2] if sous else []
    pas = int(f.size * 0.98)
    hauteur = pas * len(lignes) + (len(ls) * 54 + 30 if ls else 0)
    y0 = y_bas - hauteur
    d = ImageDraw.Draw(img)

    def dessiner(dd, force=None):
        for i, (l, coul) in enumerate(lignes):
            p = bb.ease((tl - 0.08 * i) / 0.45)
            if force and p < 0.15:
                continue
            ecrire(dd, M, y0 + pas * (i + 1) + int(40 * (1 - p)), l, f, force or coul + (int(255 * p),),
                   track=-int(f.size * 0.025))
        p = bb.ease((tl - 0.35) / 0.45)
        for k, s in enumerate(ls):
            ecrire(dd, M, y0 + pas * len(lignes) + 62 + 54 * k, s, fs, force or GRIS + (int(255 * p),))

    bb.ombre(img, lambda dd, c: dessiner(dd, c))
    dessiner(d)
    p = bb.ease(tl / 0.5)
    d.rectangle((M - 34, y0 + 18, M - 30, y0 + 18 + (hauteur + 10) * p), fill=VIOLET)
    if ls:
        d.rectangle((M, y_bas + 26, M + 70 * p, y_bas + 30), fill=VIOLET)


def carte_chiffre(img, valeur, libelle, tl, y=1150):
    nombre, unite = bb.decouper_chiffre(valeur)
    p = bb.ease(tl / 0.5)
    a, dy = int(255 * p), int(40 * (1 - p))
    f = police(900, 240 if len(nombre) <= 4 else 180)
    fl = police(500, 46)
    ll = couper(libelle, fl, W - 2 * M - 40)[:3]

    def dessiner(dd, force=None):
        if nombre == "N°":
            x = ecrire(dd, M - 4, y + dy, "N°", police(900, int(f.size * 0.56)), force or VIOLET_TXT + (a,))
            ecrire(dd, x + 6, y + dy, unite, f, force or BLANC + (a,), track=-8)
        else:
            x = ecrire(dd, M - 6, y + dy, nombre, f, force or BLANC + (a,), track=-8)
            if unite:
                ecrire(dd, x + 10, y + dy, unite, police(900, int(f.size * 0.6)), force or VIOLET_TXT + (a,))
        for k, l in enumerate(ll):
            ecrire(dd, M, y + 72 + 56 * k + dy, l, fl, force or BLANC + (a,))

    bb.ombre(img, lambda dd, c: dessiner(dd, c), rayon=18)
    d = ImageDraw.Draw(img)
    dessiner(d)
    pts = [(600, y - 70), (680, y - 90), (740, y - 120), (800, y - 114), (860, y - 160), (920, y - 172), (980, y - 230)]
    n = max(2, int(len(pts) * p))
    d.line(pts[:n], fill=VIOLET, width=4)
    for q in pts[1:n]:
        d.ellipse((q[0] - 6, q[1] - 6, q[0] + 6, q[1] + 6), fill=VIOLET)


def sous_titres(img, t, grp, y=1460):
    g = next((g for g in grp if g[0] <= t < g[1]), None)
    if not g:
        return
    debut, _, mots = g
    p = bb.ease((t - debut) / 0.12)
    lignes, x = [[]], M
    for mot, t0 in mots:
        lm = F_ST.getlength(mot + " ")
        if x + lm > W - M and lignes[-1]:
            lignes.append([])
            x = M
        lignes[-1].append((mot, t0, x))
        x += lm
    lignes = lignes[:2]
    dits = [m[1] for m in mots if m[1] <= t]
    courant = dits[-1] if dits else None
    y0 = y - 92 * (len(lignes) - 1)

    def dessiner(dd, force=None):
        for i, ligne in enumerate(lignes):
            for mot, t0, xm in ligne:
                coul = VIOLET_TXT if t0 == courant else BLANC
                a = int(255 * p) if t0 <= t else int(140 * p)
                ecrire(dd, xm, y0 + 92 * i + int(14 * (1 - p)), mot, F_ST, force or coul + (a,), track=-2)

    bb.ombre(img, lambda dd, c: dessiner(dd, c), rayon=14, force=190)
    dessiner(ImageDraw.Draw(img))


def carte_fin(tl, n):
    img = bb.fond_noir(W, H)
    img.alpha_composite(bb.arcs(W, H, ("bas-droite", "haut-gauche"), 1.0))
    p = bb.ease(tl / 0.7)
    lg = bb.logo(300, eclat=-0.3 + 1.6 * ((tl % 2.2) / 2.2))
    lg.putalpha(lg.getchannel("A").point(lambda v: int(v * p)))
    img.alpha_composite(lg, ((W - lg.width) // 2, 640 - int(30 * (1 - p))))
    d = ImageDraw.Draw(img)
    a = int(255 * bb.ease((tl - 0.3) / 0.6))
    fn = police(500, 56)
    ecrire(d, (W - largeur(nom_page(), fn, 30)) / 2, 1100, nom_page(), fn, BLANC + (a,), track=30)
    tag = "RAP  ·  CULTURE  ·  ACTUALITÉ"
    ft = police(500, 25)
    ecrire(d, (W - largeur(tag, ft, 8)) / 2, 1172, tag, ft, GRIS + (a,), track=8)
    a2 = int(255 * bb.ease((tl - 0.7) / 0.6))
    f = police(500, 30)
    q1 = "PLUS QU'UNE ACTU,"
    ecrire(d, (W - largeur(q1, f, 10)) / 2, 1330, q1, f, BLANC + (a2,), track=10)
    x = (W - largeur("UNE CULTURE.", f, 10)) / 2
    x = ecrire(d, x, 1380, "UNE ", f, BLANC + (a2,), track=10)
    ecrire(d, x + 10, 1380, "CULTURE.", f, VIOLET_TXT + (a2,), track=10)
    a3 = np.asarray(img.convert("RGB")).astype(np.float32) + GRAINS[n % len(GRAINS)][..., None]
    return Image.fromarray(a3.clip(0, 255).astype(np.uint8)).convert("RGBA")


# ------------------------------------------------------------------ montage
def _decouper(mots, t_fin_voix, post):
    """Bornes des plans : accroche (1re phrase), parties (~2,4 s, coupées entre deux mots), question."""
    fins_phrase = [m[2] for m in mots if m[0].endswith((".", "?", "!"))]
    t_accroche = next((t for t in fins_phrase if 1.8 <= t <= 3.8), min(2.9, t_fin_voix))
    q = None
    if mots and mots[-1][0].endswith("?"):
        debut_derniere = [m for i, m in enumerate(mots) if i == 0 or mots[i - 1][0].endswith((".", "?", "!"))]
        q = debut_derniere[-1][1] - 0.12 if debut_derniere else None
        if q is not None and q <= t_accroche + 1.2:
            q = None
    fin_milieu = q if q else t_fin_voix
    debuts = [m[1] for m in mots if t_accroche + 0.8 < m[1] < fin_milieu - 0.8]
    bornes, t = [t_accroche], t_accroche
    while fin_milieu - t > PLAN * 1.4:
        cible = t + PLAN
        t = min(debuts, key=lambda x: abs(x - cible)) if debuts else cible
        if t <= bornes[-1] + 1.0:
            t = bornes[-1] + PLAN
        bornes.append(t)
    return t_accroche, bornes, fin_milieu, q


def groupes(mots, t0, t1):
    gs, cur = [], []
    for m in mots:
        if not (t0 - 0.05 <= m[1] < t1):
            continue
        if cur and (len(cur) >= 4 or m[1] - cur[-1][2] > 0.25 or cur[-1][0].endswith((".", "?", ",", "!"))):
            gs.append(cur)
            cur = []
        cur.append(m)
    if cur:
        gs.append(cur)
    out = []
    for i, g in enumerate(gs):
        fin = min(gs[i + 1][0][1] if i + 1 < len(gs) else 99, g[-1][2] + 0.45)
        out.append((max(g[0][1], t0), fin, [(re.sub(r"[,;:]+$", "", m[0]), m[1]) for m in g]))
    return out


def fabriquer(post, medias, texte_voix, dossier, prefixe, diag):
    """Renvoie (chemin du Reel .mp4, chemin de la couverture .jpg)."""
    from bot.da_bruit import Choix
    dossier = Path(dossier)
    tmp = dossier / f"{prefixe}-reel-bruit"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    texte_voix = voix.preparer(texte_voix) if texte_voix else texte_voix
    audio = voix.lire(texte_voix, dossier / f"{prefixe}-audio", diag) if texte_voix else None
    duree_voix = voix.duree(audio) if audio else 8.0
    mots = mots_minutes(texte_voix, audio, diag) if audio else []
    t_fin_voix = (mots[-1][2] if mots else DELAI + duree_voix) + 0.25
    t_accroche, bornes, fin_milieu, t_question = _decouper(mots, t_fin_voix, post)
    t_fin = max(t_fin_voix, 4.5)
    total = t_fin + FIN

    v = medias.get("video")
    pool = list(medias.get("images") or []) + (list(v["images"])[:3] if v else [])
    choix = Choix(pool)
    kickers = [s.get("rubrique") for s in (post.get("slides") or []) if s.get("rubrique")] or ["Culture"]
    chiffre = (post.get("chiffre") or "").strip()
    plans = [Plan(choix.prendre(source_dabord=True), 0, t_accroche, post.get("rubrique") or "Breaking news")]
    for i, b in enumerate(bornes):
        fin = bornes[i + 1] if i + 1 < len(bornes) else fin_milieu
        if fin - b < 0.6:
            continue
        kicker = (("Classements" if (post.get("rubrique") or "").lower() == "classements" else "Décryptage")
                  if (i == 0 and chiffre) else kickers[(i - (1 if chiffre else 0)) % len(kickers)])
        plans.append(Plan(choix.prendre(), b, fin, kicker))
    if t_question:
        plans.append(Plan(choix.prendre(source_dabord=True), t_question, t_fin, "Et toi ?"))
    else:
        plans[-1].fin = t_fin
    total_cartes = len(plans) + 1
    grp = groupes(mots, t_accroche, t_question or t_fin)
    q1, q2 = post.get("question_haut") or "Et toi,", post.get("question_bas") or "t'en penses quoi ?"

    def image(t, n):
        if t >= t_fin:
            return carte_fin(t - t_fin, n)
        k = next((i for i, p in enumerate(plans) if p.debut <= t < p.fin), len(plans) - 1)
        plan = plans[k]
        tl = t - plan.debut
        img = plan.image(t)
        if k == 0 or plan.kicker == "Et toi ?":
            img.alpha_composite(bb.arcs(W, H, ("bas-droite", "haut-gauche"), 0.9))
        entete(img, plan.kicker, bb.ease(tl / 0.4))
        pied(img, k + 1, total_cartes)
        if k == 0:
            bloc_titre(img, post.get("titre_haut") or "", post.get("titre_bas") or "",
                       post.get("chiffre_texte") or "", tl)
        elif plan.kicker == "Et toi ?":
            bloc_titre(img, q1, q2, "", tl, y_bas=1420, taille=112)
        else:
            if k == 1 and chiffre:
                carte_chiffre(img, chiffre, post.get("chiffre_texte") or "", tl)
            sous_titres(img, t, grp, y=1460 if plan.mode != "haut" else 1500)
        if 0 < tl < 0.12 and k > 0:
            img.alpha_composite(Image.new("RGBA", (W, H), VIOLET + (int(70 * (1 - tl / 0.12)),)))
        return img

    muet = tmp / "muet.mp4"
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                           "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "veryfast",
                           "-crf", "21", "-pix_fmt", "yuv420p", str(muet)], stdin=subprocess.PIPE)
    try:
        for n in range(int(total * FPS)):
            ff.stdin.write(image(n / FPS, n).convert("RGB").tobytes())
        ff.stdin.close()
    except BrokenPipeError:
        pass
    if ff.wait() != 0:
        raise RuntimeError("ffmpeg n'a pas pu créer les images du Reel")
    mix = mixer_audio(audio, total, tmp / "mix.wav", diag)
    sortie = dossier / f"{prefixe}-reel.mp4"
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(muet)]
    cmd += ["-i", str(mix)] if mix else ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"]
    cmd += ["-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-ar", "44100",
            "-t", f"{total:.2f}", "-movflags", "+faststart", str(sortie)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"assemblage du Reel impossible : {r.stderr[-200:]}")
    couv = dossier / f"{prefixe}-reel-couverture.jpg"
    image(1.6, 48).convert("RGB").save(couv, "JPEG", quality=92)
    diag.append(f"  reel LE BRUIT · {total:.1f} s · {len(plans)} plans · "
                f"{'voix' if audio else 'sans voix'}{' + musique' if musique() else ''}")
    shutil.rmtree(tmp, ignore_errors=True)
    return sortie, couv


def couverture(post, medias):
    """Image de couverture du Reel (accroche) sans fabriquer la vidéo."""
    from bot.da_bruit import Choix
    pool = list(medias.get("images") or [])
    plan = Plan(Choix(pool).prendre(source_dabord=True), 0, 3, post.get("rubrique") or "Breaking news")
    img = plan.image(1.6)
    img.alpha_composite(bb.arcs(W, H, ("bas-droite", "haut-gauche"), 0.9))
    entete(img, plan.kicker)
    bloc_titre(img, post.get("titre_haut") or "", post.get("titre_bas") or "", post.get("chiffre_texte") or "", 2.0)
    return img.convert("RGB")
