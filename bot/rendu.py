"""Rendu des carrousels 1080x1350 selon la DA C'EST TOMBÉ."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

import config

RACINE = Path(__file__).resolve().parent.parent
ANTON = str(RACINE / "fonts" / "Anton-Regular.ttf")
GROTESK = str(RACINE / "fonts" / "SpaceGrotesk.ttf")

W, H, PAD = 1080, 1350, 80
NOIR, BLANC, GRIS, FILET = "#0B0B0C", "#F2F0EA", "#8A8A85", "#2A2A28"
ACCENTS = {"GAMING": "#C8FF2E", "RAP FR": "#FF5A1F"}
PHOTO_H = 680


def anton(size):
    return ImageFont.truetype(ANTON, size)


def grotesk(size, weight):
    f = ImageFont.truetype(GROTESK, size)
    f.set_variation_by_axes([weight])
    return f


def spaced(d, x, y, text, font, fill, spacing, anchor="lm"):
    for ch in text:
        d.text((x, y), ch, font=font, fill=fill, anchor=anchor)
        x += d.textlength(ch, font=font) + spacing
    return x


def spaced_w(d, text, font, spacing):
    return sum(d.textlength(c, font=font) for c in text) + spacing * max(0, len(text) - 1)


def arrow(d, x, y, h, color, stroke):
    s = h / 34
    d.line([(x + 12 * s, y + 2 * s), (x + 12 * s, y + 30 * s)], fill=color, width=stroke)
    d.line([(x + 3 * s, y + 21 * s), (x + 12 * s, y + 30 * s), (x + 21 * s, y + 21 * s)],
           fill=color, width=stroke, joint="curve")
    return 24 * s


def wrap(d, words, font, max_w):
    lines, cur = [], []
    sp = d.textlength(" ", font=font)
    for w in words:
        trial = cur + [w]
        width = sum(d.textlength(t, font=font) for t, _ in trial) + sp * (len(trial) - 1)
        if width > max_w and cur:
            lines.append(cur)
            cur = [w]
        else:
            cur = trial
    if cur:
        lines.append(cur)
    return lines


def typo(t):
    return (t or "").replace("'", "’")


def colored_words(titre, mot_cle, accent):
    titre, mot_cle = typo(titre).upper(), typo(mot_cle).upper()
    if mot_cle and mot_cle in titre:
        a, b = titre.split(mot_cle, 1)
        return ([(w, BLANC) for w in a.split()] + [(w, accent) for w in mot_cle.split()]
                + [(w, BLANC) for w in b.split()])
    return [(w, BLANC) for w in titre.split()]


def logo(d, x, y, accent, size=44):
    aw = arrow(d, x, y, size, accent, 5 if size >= 40 else 4)
    d.text((x + aw + 14, y + size / 2), "C’EST TOMBÉ", font=anton(size), fill=BLANC, anchor="lm")


def tag(d, x1, y, label, accent):
    f = grotesk(26, 700)
    x0 = x1 - spaced_w(d, label, f, 4) - 48
    d.rectangle([x0, y, x1, y + 54], fill=accent)
    spaced(d, x0 + 24, y + 27, label, f, NOIR, 4)


def titre_bloc(d, words, zone_top, zone_bot, taille_max, taille_min=64):
    size = taille_max
    while True:
        tf = anton(size)
        lines = wrap(d, words, tf, W - 2 * PAD)
        lh = int(size * 1.16)
        if lh * len(lines) <= zone_bot - zone_top or size <= taille_min:
            break
        size -= 4
    y = zone_top + max(0, (zone_bot - zone_top - lh * len(lines)) // 2)
    sp = d.textlength(" ", font=tf)
    for line in lines:
        x = PAD
        for w, col in line:
            d.text((x, y + lh * 0.86), w, font=tf, fill=col, anchor="ls")
            x += d.textlength(w, font=tf) + sp
        y += lh


def pied_couverture(d, source, accent):
    foot_y = H - PAD - 15
    d.line([(PAD, foot_y - 40), (W - PAD, foot_y - 40)], fill=FILET, width=2)
    spaced(d, PAD, foot_y, f"SOURCE · {source}", grotesk(24, 500), GRIS, 3)
    gf, gl = grotesk(26, 700), "GLISSE  →"
    spaced(d, W - PAD - spaced_w(d, gl, gf, 3), foot_y, gl, gf, accent, 3)
    return foot_y


# ---------------------------------------------------------------- slide 1
def couverture(post, accent, photo):
    img = Image.new("RGB", (W, H), NOIR)
    d = ImageDraw.Draw(img)
    words = colored_words(post["titre"], post.get("mot_cle"), accent)

    if photo is not None:
        img.paste(ImageOps.fit(photo, (W, PHOTO_H), method=Image.LANCZOS, centering=(0.5, 0.4)), (0, 0))
        chip_w = 24 + 14 + d.textlength("C’EST TOMBÉ", font=anton(34)) + 40
        d.rectangle([64, 64, 64 + chip_w, 64 + 62], fill=NOIR)
        logo(d, 84, 78, accent, size=34)
        tag(d, W - 64, 68, post["categorie"], accent)
        d.rectangle([0, PHOTO_H, W, PHOTO_H + 12], fill=accent)
        foot_y = pied_couverture(d, post["source"], accent)
        titre_bloc(d, words, PHOTO_H + 12 + 48, foot_y - 80, 112)
    else:  # pas de photo : version « template seul », gros titre centré
        logo(d, PAD, PAD, accent)
        tag(d, W - PAD, PAD, post["categorie"], accent)
        foot_y = pied_couverture(d, post["source"], accent)
        top = PAD + 54 + 110
        d.rectangle([PAD, top + 4, PAD + 18, top + 22], fill=accent)
        spaced(d, PAD + 34, top + 13, "À L’INSTANT", grotesk(26, 500), GRIS, 5)
        titre_bloc(d, words, top + 70, foot_y - 90, 136)
    return img


# ---------------------------------------------------------------- slides texte
BODY_TOP = PAD + 54 + 90
FOOT_TOP = H - PAD - 90
BODY_LH = int(40 * 1.45)
SEC_H = 26 + 24
FIN_H = 350


def paginer(d, sections):
    bf = grotesk(40, 400)
    pages, page, y = [], [], BODY_TOP
    limite = FOOT_TOP - 40
    for sec in sections:
        mots = [(w, None) for w in typo(sec["texte"]).split()]
        lines = [" ".join(t for t, _ in l) for l in wrap(d, mots, bf, W - 2 * PAD)]
        hauteur = SEC_H + BODY_LH * len(lines)
        besoin = hauteur if len(lines) <= 6 else SEC_H + BODY_LH * 2
        if page and y + besoin > limite:
            pages.append(page)
            page, y = [], BODY_TOP
        page.append(("titre", typo(sec["titre"])))
        y += SEC_H
        for ln in lines:
            if y + BODY_LH > limite:
                pages.append(page)
                page, y = [], BODY_TOP
            page.append(("ligne", ln))
            y += BODY_LH
        page.append(("espace", None))
        y += 44
    if page:
        pages.append(page)
    return pages


def hauteur_page(blocs):
    return BODY_TOP + sum(SEC_H if k == "titre" else BODY_LH if k == "ligne" else 44 for k, _ in blocs)


def slide_texte(post, accent, blocs, num, total, fin):
    img = Image.new("RGB", (W, H), NOIR)
    d = ImageDraw.Draw(img)
    logo(d, PAD, PAD, accent)
    tag(d, W - PAD, PAD, post["categorie"], accent)
    bf, sf = grotesk(40, 400), grotesk(26, 700)
    y = BODY_TOP
    for kind, val in blocs:
        if kind == "titre":
            d.rectangle([PAD, y + 4, PAD + 16, y + 20], fill=accent)
            spaced(d, PAD + 32, y + 13, val.upper(), sf, accent, 4)
            y += SEC_H
        elif kind == "ligne":
            d.text((PAD, y + BODY_LH * 0.74), val, font=bf, fill=BLANC, anchor="ls")
            y += BODY_LH
        else:
            y += 44
    if fin:
        y = max(y + 20, FOOT_TOP - 330)
        d.line([(PAD, y), (W - PAD, y)], fill=FILET, width=2)
        y += 48
        meta = f"SOURCE · {post['source']}"
        if post.get("credit") and post["credit"].lower() not in post["source"].lower():
            meta += f" · PHOTO : {post['credit'].upper()}"
        mf = grotesk(24, 500)
        base = meta
        while spaced_w(d, meta, mf, 3) > W - 2 * PAD and len(base) > 20:
            base = base[:-1]
            meta = base.rstrip() + "…"
        spaced(d, PAD, y, meta, mf, GRIS, 3)
        y += 70
        d.text((PAD, y + 50), "ABONNE-TOI POUR PAS RATER", font=anton(64), fill=BLANC, anchor="ls")
        d.text((PAD, y + 125), "CE QUI TOMBE", font=anton(64), fill=accent, anchor="ls")
    foot_y = H - PAD - 15
    d.line([(PAD, FOOT_TOP), (W - PAD, FOOT_TOP)], fill=FILET, width=2)
    d.text((PAD, foot_y), config.HANDLE, font=grotesk(26, 700), fill=BLANC, anchor="lm")
    pf = grotesk(26, 500)
    pg = f"{num} / {total}" + ("" if fin else "   →")
    spaced(d, W - PAD - spaced_w(d, pg, pf, 3), foot_y, pg, pf, GRIS, 3)
    return img


def carrousel(post, photo, dossier, prefixe):
    """post = {categorie, titre, mot_cle, sections, source, credit}. Renvoie la liste des JPEG."""
    accent = ACCENTS.get(post["categorie"], ACCENTS["GAMING"])
    dossier = Path(dossier)
    dossier.mkdir(parents=True, exist_ok=True)
    d = ImageDraw.Draw(Image.new("RGB", (W, H)))
    pages = paginer(d, post["sections"])
    if hauteur_page(pages[-1]) > FOOT_TOP - FIN_H:
        pages.append([])               # la fin (source + abonnement) va sur une slide à part
    pages = pages[: config.MAX_SLIDES - 1]
    total = len(pages) + 1
    images = [couverture(post, accent, photo)]
    images += [slide_texte(post, accent, b, i, total, i == total) for i, b in enumerate(pages, start=2)]
    fichiers = []
    for i, im in enumerate(images, start=1):
        p = dossier / f"{prefixe}-{i}.jpg"
        im.save(p, "JPEG", quality=92, optimize=True)
        fichiers.append(p)
    return fichiers
