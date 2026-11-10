"""Reel DA v3 (forme reprise de @7run.club), 1080x1920.

- Une image toutes les ~2,4 s : extraits de la vidéo de la source et photos (zoom lent), chacun cadré sur
  son sujet, sans texte incrusté sous nos textes.
- Début : accroche en étiquettes (lime puis blanc). Puis sous-titres qui suivent la voix mot à mot, le mot
  prononcé surligné en lime ; un chiffre clé en étiquettes ; fin : la question au spectateur + le pseudo.
- Son : voix off + musique (la musique baisse quand la voix parle).
"""
import re
import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

import config
from bot import da3, placement, voix
from bot.reel import mixer_audio, musique

W, H, FPS = da3.RW, da3.RH, 30
PLAN = 2.4             # durée d'une image (s)
ACCROCHE = 2.7         # durée de l'accroche au début (s)
FIN = 3.0              # carte de fin (s)
DELAI_VOIX = 0.3       # la voix démarre 0,3 s après le début (voir mixer_audio)
BANDE_ST = (1340, 1490)   # zone des sous-titres
ZONE_LIBRE = (1180, 1500)  # aucun texte incrusté ni visage dans cette bande (sous-titres + chiffre clé)
ZONE_HAUTE = (300, 620)    # si le visage occupe le bas de l'image, les sous-titres passent en haut
GENANT = 0.012             # dans un Reel, même un petit texte incrusté visible gêne
BORD_HAUT = 260           # sous le logo et la puce


# ------------------------------------------------------------------ minutage des mots
def passages_parles(audio):
    """[(début, fin)] des passages où la voix parle (silences repérés par ffmpeg)."""
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(audio), "-af", "silencedetect=noise=-35dB:d=0.12",
                        "-f", "null", "-"], capture_output=True, text=True)
    total = voix.duree(audio)
    debuts = [float(x) for x in re.findall(r"silence_start: ([0-9.]+)", r.stderr)]
    fins = [float(x) for x in re.findall(r"silence_end: ([0-9.]+)", r.stderr)]
    passages, t = [], 0.0
    for a, b in zip(debuts, fins + [total] * (len(debuts) - len(fins))):
        if a - t > 0.08:
            passages.append((t, a))
        t = b
    if total - t > 0.08:
        passages.append((t, total))
    return passages or [(0.0, total)]


def minuter(texte, audio):
    """[(mot, début, fin)] : chaque mot placé sur le temps de parole, au prorata de sa longueur."""
    mots = texte.split()
    if not mots:
        return []
    passages = passages_parles(audio)
    parole = sum(b - a for a, b in passages)
    poids = [len(m) + 2 for m in mots]
    total = sum(poids)
    sortie, cumul = [], 0.0

    def vers_reel(tp):     # temps de parole → temps réel
        reste = tp
        for a, b in passages:
            if reste <= b - a:
                return a + reste
            reste -= b - a
        return passages[-1][1]

    for m, p in zip(mots, poids):
        t0 = cumul / total * parole
        cumul += p
        t1 = cumul / total * parole
        sortie.append((m, vers_reel(t0) + DELAI_VOIX, vers_reel(t1) + DELAI_VOIX))
    return sortie


def groupes(mots, n=3):
    out, cur = [], []
    for m in mots:
        cur.append(m)
        if len(cur) == n or re.search(r"[.,!?:;…]$", m[0]):
            out.append(cur)
            cur = []
    if cur:
        out.append(cur)
    return out


# ------------------------------------------------------------------ dessin
def sticker(d, cx, y, lignes_, taille=84):
    f = da3.police("titre", taille)
    for texte, couleur in lignes_:
        t = texte.upper()
        f = da3.ajuste(t, "titre", taille, W - 140, mini=50)
        w = d.textlength(t, font=f)
        h = f.size * 1.12
        d.rectangle([cx - w / 2 - 18, y, cx + w / 2 + 18, y + h], fill=couleur)
        d.text((cx, y + h * 0.80), t, font=f, fill=da3.NOIR, anchor="ms")
        y += h + 6
    return y


def sous_titres(d, mots, actif, y=1430):
    f = da3.police("titre", 64)
    sp = 20
    ws = [d.textlength(m.upper(), font=f) for m in mots]
    while sum(ws) + sp * (len(mots) - 1) > W - 120 and f.size > 40:
        f = da3.police("titre", f.size - 4)
        ws = [d.textlength(m.upper(), font=f) for m in mots]
    x = W / 2 - (sum(ws) + sp * (len(mots) - 1)) / 2
    for k, (m, w) in enumerate(zip(mots, ws)):
        if k == actif:
            d.rectangle([x - 10, y - f.size * 0.97, x + w + 10, y + f.size * 0.22], fill=da3.LIME)
            d.text((x, y), m.upper(), font=f, fill=da3.NOIR, anchor="ls")
        else:
            d.text((x, y), m.upper(), font=f, fill=da3.BLANC, anchor="ls")
        x += w + sp


def carte_fin(d, post):
    q1, q2 = post.get("question_haut") or "Et toi,", post.get("question_bas") or "t'en penses quoi ?"
    ft = da3.titre_2_lignes(q1, q2, taille=104, largeur_max=W - 140)
    d.text((W / 2, 900), q1.upper(), font=ft, fill=da3.BLANC, anchor="ms")
    d.text((W / 2, 900 + int(ft.size * 1.15)), q2.upper(), font=ft, fill=da3.LIME, anchor="ms")
    y = 900 + int(ft.size * 1.15) + 80
    fl = da3.police("texte_b", 36)
    pw = d.textlength(config.HANDLE, font=fl) + 84
    d.rounded_rectangle([W / 2 - pw / 2, y, W / 2 + pw / 2, y + 74], radius=37, outline=da3.BLANC, width=3)
    d.text((W / 2, y + 50), config.HANDLE, font=fl, fill=da3.BLANC, anchor="ms")
    d.text((W / 2, y + 145), "Abonne-toi pour ne rien rater", font=da3.police("texte", 30),
           fill=(225, 225, 220), anchor="ms")


# ------------------------------------------------------------------ plans (images qui bougent)
class Photo:
    """Photo qui bouge lentement. Plein écran si elle s'y prête ; sinon « encadrée » : la photo entière
    au-dessus des sous-titres, sur un fond flou de la même photo (comme les photos d'archive chez 7RUN)."""

    def __init__(self, media, choix, duree, sens=1, encadree=False):
        self.duree, self.sens, self.choix, self.encadree = duree, sens, choix, encadree
        img = media["img"]
        if encadree:
            img = recadrer_encadre(img, media["analyse"])
            fondu = img.copy()
            e = max(W / img.width, H / img.height)
            fondu = fondu.resize((int(img.width * e) + 2, int(img.height * e) + 2), Image.BILINEAR)
            fondu = fondu.crop(((fondu.width - W) // 2, (fondu.height - H) // 2,
                                (fondu.width - W) // 2 + W, (fondu.height - H) // 2 + H))
            fondu = fondu.filter(ImageFilter.GaussianBlur(28)).convert("RGBA")
            fondu.alpha_composite(Image.new("RGBA", (W, H), da3.NOIR + (120,)))
            self.fond = fondu.convert("RGB")
            boite_w, boite_h = BOITE
            k = min(boite_w / img.width, boite_h / img.height)
            self.photo = img.resize((int(img.width * k * 1.06), int(img.height * k * 1.06)), Image.LANCZOS)
            self.taille = (int(img.width * k), int(img.height * k))
            self.centre = (W // 2, 300 + boite_h // 2)
            self.choix = {"zone": "bas", "y0": 300 + boite_h // 2 - self.taille[1] // 2}
        else:
            x0, y0, cw, ch = choix["fenetre"]
            self.base = img.crop((int(x0), int(y0), int(x0 + cw), int(y0 + ch))).resize(
                (int(W * 1.1), int(H * 1.1)), Image.LANCZOS)

    def image(self, t):
        k = min(1.0, max(0.0, t / self.duree))
        k = k * k * (3 - 2 * k)
        if self.encadree:
            im = self.fond.copy()
            pw, ph = self.photo.size
            z = 1 + 0.05 * (k if self.sens > 0 else 1 - k)
            vw, vh = pw / z, ph / z
            x, y = (pw - vw) / 2, (ph - vh) / 2
            vue = self.photo.resize(self.taille, Image.BILINEAR, box=(x, y, x + vw, y + vh))
            ombre = Image.new("RGBA", (self.taille[0] + 60, self.taille[1] + 60), (0, 0, 0, 0))
            ImageDraw.Draw(ombre).rectangle([30, 36, 30 + self.taille[0], 36 + self.taille[1]], fill=(0, 0, 0, 150))
            ombre = ombre.filter(ImageFilter.GaussianBlur(14))
            cx, cy = self.centre
            im.paste(ombre, (cx - self.taille[0] // 2 - 30, cy - self.taille[1] // 2 - 30), ombre)
            im.paste(vue, (cx - self.taille[0] // 2, cy - self.taille[1] // 2))
            return im
        z = 1 + 0.1 * (k if self.sens > 0 else 1 - k)
        bw, bh = self.base.size
        vw, vh = bw / z, bh / z
        x = (bw - vw) / 2 * (1 + 0.4 * (2 * k - 1) * self.sens)
        return self.base.resize((W, H), Image.BILINEAR, box=(x, (bh - vh) / 2, x + vw, (bh - vh) / 2 + vh))


BOITE = (W - 80, ZONE_LIBRE[0] - 300)      # photo encadrée : entre la puce et les sous-titres
HAUTEUR_MIN = 820                          # plein écran : pas plus de ~2,3x d'agrandissement (sinon flou)


def recadrer_encadre(img, analyse):
    """Photo encadrée : une photo très large est recoupée vers le format de la boîte, autour du sujet
    (visage, objet), pour qu'elle reste grande ; si le sujet ne tient pas dans la découpe, photo entière."""
    cible = BOITE[0] / BOITE[1]
    if img.width / img.height <= cible * 1.12:
        return img
    sujet = analyse.get("sujet")
    for rapport in (cible, 4 / 3, 16 / 10):
        cw = int(img.height * rapport)
        if cw >= img.width:
            break
        if sujet:
            sx0, _, sx1, _ = sujet
            if sx1 - sx0 > cw * 0.96:
                continue                          # le sujet serait coupé : format plus large
            cx = (sx0 + sx1) / 2
        else:
            cx = img.width / 2
        x0 = int(min(max(0, cx - cw / 2), img.width - cw))
        return img.crop((x0, 0, x0 + cw, img.height))
    return img


def plan_photo(media, accroche, sens):
    """Plein écran si le sujet y tient entier et proprement (photo paysage comprise, recadrée sur le sujet) ;
    sinon photo encadrée. Renvoie (plan, note : plus haut = meilleur)."""
    c = _cadre_photo(media, accroche)
    img, an = media["img"], media["analyse"]
    paysage = img.width / img.height > 1.15
    if an.get("visages"):
        sujet_ok = c.get("visages_visibles", 0) >= 0.99 and c.get("sujet_visible", 1) >= 0.7
    else:
        sujet_ok = c.get("sujet_visible", 1) >= (0.85 if paysage else 0.8)
    if paysage:     # une photo paysage en plein écran n'en garde qu'un tiers : il faut un vrai sujet
        sujet_ok = sujet_ok and (an.get("sujet") is not None or an.get("visages"))
    assez_grande = c["fenetre"][3] >= HAUTEUR_MIN
    if c["propre"] and sujet_ok and assez_grande:
        return Photo(media, c, PLAN, sens), 2
    return Photo(media, c, PLAN, sens, encadree=True), 1


class Clip:
    def __init__(self, dossier, video, debut, choix, duree):
        self.dossier, self.duree, self.choix = Path(dossier), duree, choix
        self.dossier.mkdir(parents=True, exist_ok=True)
        f = video["facteur"]
        x0, y0, cw, ch = [v * f for v in choix["fenetre"]]
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{debut:.2f}", "-t", f"{duree + 0.2:.2f}",
                        "-i", str(video["chemin"]), "-vf",
                        f"crop={int(cw)}:{int(ch)}:{int(x0)}:{int(y0)},scale={W}:{H}:flags=bicubic,fps={FPS}",
                        "-q:v", "3", str(self.dossier / "%04d.jpg")], check=True)
        self.images = sorted(self.dossier.glob("*.jpg"))
        if not self.images:
            raise RuntimeError("extrait vidéo vide")

    def image(self, t):
        return Image.open(self.images[min(len(self.images) - 1, int(t * FPS))]).convert("RGB")


FIXES = {"logo": (55, 55, 480, 125), "puce": (55, 140, 760, 200)}


def _cadre_photo(media, accroche=False):
    """Cadrage d'une photo : sujet entier, rien d'important sous les sous-titres (ni sous l'accroche)."""
    return placement.choisir(media["img"], media["analyse"], W, H, **_zones(accroche), fixes=FIXES, genant=GENANT)


def _zones(accroche):
    """Où vont nos textes : l'accroche en haut ou au milieu ; les sous-titres en bas (ou en haut si besoin)."""
    if accroche:
        return {"hauteur_bloc": 260, "zones": ("haut", "milieu"), "bord_haut": 330}
    return {"hauteur_bloc": ZONE_LIBRE[1] - ZONE_LIBRE[0], "zones": ("bas", "haut"), "bord_haut": ZONE_HAUTE[0],
            "bord_bas": H - ZONE_LIBRE[1]}


def _cadre_clip(video, deja, accroche=False):
    """Meilleur passage de PLAN secondes de la vidéo (pas déjà utilisé) et son cadrage."""
    images = video["analyses"]
    persist = placement._persistants(images) if len(images) > 2 else [a["textes"] for _, _, a in images]
    if sum(1 for _, _, a in images if a["textes"]) > 0.4 * len(images):
        # sous-titres incrustés presque partout : on recadre pour les sortir de l'image sur tout l'extrait
        tous = [b for g in persist for b in g]
        persist = [tous for _ in persist]
    pas = video["pas"]
    meilleur = None
    for i in range(0, len(images), max(1, int(round(PLAN / pas)))):
        t = images[i][0] - pas / 2
        if t + PLAN > video["duree"] or any(abs(t - u) < PLAN for u in deja):
            continue
        idx = [j for j, e in enumerate(images) if t - pas / 2 <= e[0] <= t + PLAN + pas / 2]
        c = placement.choisir(images[idx[len(idx) // 2]][1], placement._union([images[j] for j in idx],
                              [persist[j] for j in idx]), W, H, **_zones(accroche), fixes=FIXES, genant=GENANT,
                              echelle_source=video.get("facteur", 1.0))
        note = (c["propre"], -(c["cout"] + 0.5 * t))
        if meilleur is None or note > meilleur[0]:
            meilleur = (note, max(0.0, t), c)
    return (meilleur[1], meilleur[2]) if meilleur and meilleur[0][0] else (None, None)


def construire_plans(medias, n, tmp, diag):
    """n plans : on commence par la source (extrait vidéo ou photo de la source), puis on alterne."""
    v = medias.get("video")
    images = list(medias.get("images") or [])
    sources = [m for m in images if m.get("origine", "source") == "source"]
    autres = [m for m in images if m.get("origine") == "autre"]
    plans, deja, utilise = [], [], {}
    ordre_photos = sources + autres
    for i in range(n):
        accroche = i == 0
        veut_video = v is not None and (i % 2 == 0 or not ordre_photos)
        plan = None
        if veut_video:
            debut, c = _cadre_clip(v, deja, accroche)
            if c is not None:
                try:
                    plan = Clip(tmp / f"clip{i}", v, debut, c, PLAN)
                    deja.append(debut)
                except Exception as ex:
                    diag.append(f"  reel · extrait vidéo impossible : {str(ex)[:100]}")
        if plan is None:
            pool = (sources + autres) if (sources or autres) else (v["images"] if v else [])
            if not pool:
                pool = [{"img": da3.fond_neutre((W, H)), "analyse": {"textes": [], "visages": [], "sujet": None},
                         "nom": "neutre"}]
            if accroche and sources:
                pool = sources          # la 1re image parle toujours du sujet
            meilleur = None
            for m in pool:
                p, note = plan_photo(m, accroche, 1 if i % 2 else -1)
                cle = (-utilise.get(m["nom"], 0), note - (1.5 if da3.flou(m, pool) else 0), -pool.index(m))
                if meilleur is None or cle > meilleur[0]:
                    meilleur = (cle, p, m)
            plan = meilleur[1]
            utilise[meilleur[2]["nom"]] = utilise.get(meilleur[2]["nom"], 0) + 1
        plans.append(plan)
    return plans


# ------------------------------------------------------------------ assemblage
def fabriquer(post, medias, texte_voix, dossier, prefixe, diag):
    """Renvoie (chemin du Reel .mp4, chemin de la couverture .jpg)."""
    dossier = Path(dossier)
    tmp = dossier / f"{prefixe}-reel3"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    texte_voix = voix.preparer(texte_voix) if texte_voix else texte_voix   # les sous-titres = ce qui est lu
    audio = voix.lire(texte_voix, dossier / f"{prefixe}-audio", diag) if texte_voix else None
    duree_voix = voix.duree(audio) if audio else 8.0
    mots = minuter(texte_voix, audio) if audio else []
    grp = groupes(mots)
    t_fin = max(ACCROCHE + PLAN, DELAI_VOIX + duree_voix + 0.3)
    total = t_fin + FIN
    n_plans = max(2, int(round(t_fin / PLAN)))
    plans = construire_plans(medias, n_plans + 1, tmp, diag)
    bornes = [i * t_fin / n_plans for i in range(n_plans)] + [t_fin]
    voile = da3.degrade((W, H), haut=0.35, debut=0.55, bas=0.55)
    chiffre = (post.get("chiffre") or "").strip()
    stat = None
    if chiffre and len(grp) > 2:      # le chiffre clé s'affiche sur le 2e groupe de mots après l'accroche
        apres = [g for g in grp if g[0][1] >= ACCROCHE]
        if apres:
            stat = (apres[0][0][1], apres[0][-1][2] + 0.3)
    accroche = [(post.get("accroche_reel_haut") or post["titre_haut"], da3.LIME),
                (post.get("accroche_reel_bas") or post["titre_bas"], da3.BLANC)]
    libelle = post.get("chiffre_libelle") or post.get("chiffre_texte") or ""
    if getattr(plans[0], "encadree", False):
        y_accroche = ZONE_LIBRE[0] + 40            # sous la photo encadrée, jamais dessus
    else:
        y_accroche = (plans[0].choix["y0"] if plans[0].choix.get("zone") in ("haut", "milieu") else 400)

    def image(t):
        if t >= t_fin:
            plan_courant = plans[-1]
            im = plan_courant.image(t - t_fin).convert("RGBA")
        else:
            i = min(n_plans - 1, max(k for k in range(n_plans) if bornes[k] <= t))
            plan_courant = plans[i]
            im = plan_courant.image(t - bornes[i]).convert("RGBA")
        im.alpha_composite(voile)
        if t >= t_fin:
            im.alpha_composite(Image.new("RGBA", (W, H), da3.NOIR + (int(185 * min(1, (t - t_fin) / 0.3)),)))
        couche = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(couche)
        da3.logo(d, 62, 70, 52)
        if t >= t_fin:
            carte_fin(d, post)
        else:
            if t >= ACCROCHE:
                da3.puce(d, 62, 150, post.get("rubrique") or "Actu", post.get("accroche_couv") or "")
            if t < ACCROCHE:
                sticker(d, W / 2, y_accroche, accroche)
            else:
                en_haut = plan_courant.choix.get("zone") == "haut"
                if stat and stat[0] <= t < stat[1]:
                    sticker(d, W / 2, ZONE_HAUTE[0] + 20 if en_haut else ZONE_LIBRE[0] + 20,
                            [(chiffre, da3.LIME)] + ([(libelle[:28], da3.BLANC)] if libelle else []))
                else:
                    for g in grp:
                        if g[0][1] - 0.05 <= t < g[-1][2] + 0.05:
                            actif = max([k for k, m in enumerate(g) if m[1] <= t] or [0])
                            sous_titres(d, [re.sub(r"[.,;:!?…]+$", "", m[0]) for m in g], actif,
                                        y=ZONE_HAUTE[0] + 200 if en_haut else 1450)
                            break
        im.alpha_composite(da3.avec_ombre(couche, rayon=8, force=0.7))
        return im.convert("RGB")

    muet = tmp / "muet.mp4"
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                           "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "veryfast",
                           "-crf", "20", "-pix_fmt", "yuv420p", str(muet)], stdin=subprocess.PIPE)
    try:
        for k in range(int(total * FPS)):
            ff.stdin.write(image(k / FPS).tobytes())
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
    da3.couverture_reel(post, medias).save(couv, "JPEG", quality=92)
    nb_clips = sum(isinstance(p, Clip) for p in plans)
    diag.append(f"  reel · {total:.1f} s · {len(plans)} plans dont {nb_clips} extraits vidéo · "
                f"{'voix' if audio else 'sans voix'}{' + musique' if musique() else ''}")
    shutil.rmtree(tmp, ignore_errors=True)
    return sortie, couv
