# C'EST TOMBÉ — le bot

Page Instagram d'actu **gaming** et **rap FR**, 100 % automatique et gratuite.

Toutes les 30 minutes, GitHub lance le bot. S'il est l'heure de poster :

1. il lit **ActuGaming** (flux RSS) et **@rap.minute** (API officielle Instagram) ;
2. **Gemini** écarte ce qui n'est pas de l'actu (guides, soluces, promos…), note les infos et garde la meilleure ;
3. Gemini écrit le titre, les slides et la légende, **uniquement avec les faits de la source** ;
4. le bot fabrique le **carrousel** dans la DA (photo + gros titre, puis l'info complète, puis la source) ;
5. il le **publie** sur ton compte.

Réglages par défaut : 6 posts par jour, entre 9h et 23h (heure de Paris), au moins 2h entre deux posts, en alternant gaming et rap. Tout se change dans `config.py`.

---

## Ce qu'il te faut (tout est gratuit)

- le compte Instagram de la page ;
- un compte Facebook (pour créer une page Facebook et l'app Meta) ;
- un compte Google (pour la clé Gemini) ;
- un compte GitHub.

Compte environ 45 minutes pour tout installer, une seule fois. Les écrans de Meta changent souvent : si un intitulé n'est pas exactement le même, cherche le plus proche.

---

## Étape 1 — Passer le compte Instagram en Pro et le relier à une page Facebook

1. Dans Instagram : **Paramètres → Type de compte et outils → Passer à un compte professionnel**. Choisis **Créateur** (ou Entreprise).
2. Sur Facebook, crée une **page** au nom de C'EST TOMBÉ.
3. Dans les paramètres de la page Facebook (ou dans Instagram : **Paramètres → Centre de comptes**), **relie le compte Instagram à la page**.

> Sans ça, impossible de publier ni de lire @rap.minute : l'API passe par la page Facebook.

## Étape 2 — La clé Gemini (l'IA)

1. Va sur **aistudio.google.com** et connecte-toi.
2. Clique sur **Get API key → Create API key**.
3. Copie la clé et garde-la de côté. C'est ta **GEMINI_API_KEY**.

## Étape 3 — L'app Meta et la clé Instagram

1. Va sur **developers.facebook.com → Mes apps → Créer une app**. Choisis un usage lié à **Instagram / gestion de page** (type Business). Donne-lui le nom que tu veux.
2. Dans l'app, ajoute le produit **Instagram** (version « API Instagram avec connexion Facebook »).
3. Crée une **clé qui n'expire jamais** (recommandé) :
   - va sur **business.facebook.com → Paramètres → Utilisateurs → Utilisateurs système → Ajouter** (rôle Admin) ;
   - **Attribuer des éléments** : ta page Facebook, ton compte Instagram et ton app (contrôle total) ;
   - **Générer un nouveau token** : choisis ton app, expiration **Jamais**, et coche :
     `instagram_basic`, `instagram_content_publish`, `instagram_manage_insights`, `pages_show_list`, `pages_read_engagement`, `business_management`, `ads_read`.
     (`instagram_manage_insights` et `ads_read` sont exigés par Meta pour lire @rap.minute.)
   - Copie le token. C'est ton **IG_ACCESS_TOKEN**.

   > Plan B si tu bloques : l'**Explorateur de l'API Graph** (developers.facebook.com/tools/explorer) donne un token avec les mêmes permissions. Il marche pour le test, mais il expire : il faudra le remplacer.

4. **IG_USER_ID** : pas besoin de le chercher. Lance le test de l'étape 6 sans lui : le résumé t'affichera la ligne `IG_USER_ID = 1784…`. Copie ce numéro.

## Étape 4 — Les deux dépôts GitHub

1. **Dépôt du bot, privé** : crée un dépôt `cesttombe-bot` en **Private**, puis **Add file → Upload files** et dépose **tout le contenu** du dossier (y compris le dossier `.github`).
   > Si le dossier `.github` ne passe pas (ça arrive sur téléphone), crée le fichier à la main : **Add file → Create new file**, nom `.github/workflows/cesttombe.yml`, et colle le contenu du fichier.
2. **Images** : rien à faire si le dépôt `cesttombe-bot` est **public**. Le bot met les images dans sa branche `images` (remplacée à chaque post), avec le jeton automatique de GitHub. Tes clés restent cachées dans les Secrets.
   > Option si tu préfères un dépôt de code privé : crée un dépôt public `cesttombe-images`, un token (étape 5) et la variable `IMAGES_REPO`.

## Étape 5 — (optionnel, seulement avec un dépôt privé) La clé GitHub pour le dépôt d'images

1. GitHub → ta photo → **Settings → Developer settings → Personal access tokens → Fine-grained tokens → Generate new token**.
2. **Repository access** : *Only select repositories* → `cesttombe-images`.
3. **Permissions → Repository permissions → Contents** : *Read and write*.
4. Expiration : la plus longue proposée. **Note la date** : il faudra la renouveler.
5. Copie le token. C'est ton **IMAGES_TOKEN**.

## Étape 6 — Ranger les clés dans GitHub

Dans le dépôt `cesttombe-bot` : **Settings → Secrets and variables → Actions**.

Onglet **Secrets** → *New repository secret*, un par un :

| Nom | Valeur |
|---|---|
| `GEMINI_API_KEY` | la clé de l'étape 2 |
| `IG_ACCESS_TOKEN` | le token de l'étape 3 |
| `IG_USER_ID` | le numéro trouvé au test (laisse vide au tout premier test) |
| `IMAGES_TOKEN` | le token de l'étape 5 |

Onglet **Variables** → *New repository variable* :

| Nom | Valeur |
|---|---|
| `IMAGES_REPO` | `tonpseudo/cesttombe-images` |
| `PUBLICATION` | `off` (on passera à `on` à la fin) |

## Étape 7 — Le test à blanc (rien n'est publié)

1. Onglet **Actions** du dépôt (accepte d'activer les workflows si GitHub le demande).
2. **C'EST TOMBÉ → Run workflow → mode : test → Run**.
3. Ouvre l'exécution quand elle est finie (1 à 3 minutes) :
   - le **résumé** dit ce qui a marché : flux ActuGaming, lecture de @rap.minute, photos trouvées, token Meta, nombre d'infos retenues ;
   - en bas, l'artefact **carrousels-…** contient les slides et la légende générés : télécharge-le et regarde.
4. Si `IG_USER_ID` était vide, copie le numéro affiché dans le résumé, ajoute le secret, et relance le test.

**Ce que le test doit montrer :**
- `Gaming · … → HTTP 200` et des infos retenues ;
- `Rap · @rap.minute → 12 posts lus` (sinon : le compte n'est pas Pro, ou le token n'a pas les bonnes permissions) ;
- `photo · trouvée` (sinon les couvertures seront sans photo, le post part quand même) ;
- `Instagram · @tonpseudo (… abonnés)`.

## Étape 8 — Le premier vrai post

**Run workflow → mode : reel**. Un post part tout de suite. Vérifie-le sur Instagram.

## Étape 9 — Mode automatique

Dans `config.py` : `PUBLICATION_AUTO = True`. C'est tout : le bot tourne seul, toutes les 30 minutes.

Pour **mettre en pause** : remets `False`. (Une variable GitHub `PUBLICATION` = `on` / `off` a priorité sur ce réglage, si tu préfères passer par les Settings.)

---

## Réglages (`config.py`)

| Réglage | Par défaut | Rôle |
|---|---|---|
| `POSTS_PAR_JOUR` | 6 | nombre max de posts par jour |
| `HEURE_DEBUT` / `HEURE_FIN` | 9 / 23 | plage horaire (Paris) |
| `ECART_MIN_MINUTES` | 120 | temps minimum entre deux posts |
| `SCORE_MIN` | 6 | note mini de l'IA pour publier (monte-la pour être plus exigeant) |
| `COMPTES_RAP` | `["rap.minute"]` | pages Insta rap à suivre (comptes Pro) |
| `HANDLE` | `@cesttombe` | pseudo affiché sur les slides |

## Si ça ne marche pas

| Message dans le résumé | Ce qu'il faut faire |
|---|---|
| `Gaming · … → HTTP 403` sur tous les flux | ActuGaming bloque les serveurs GitHub. Le bot essaie la page de secours ; si elle échoue aussi, il faudra une autre source gaming. |
| `Rap · @rap.minute → refus de Meta` | Le token doit avoir `instagram_basic`, `instagram_manage_insights`, `pages_read_engagement` et `ads_read` (la ligne « autorisations du token » du résumé les liste). Sinon, le compte suivi n'est pas Pro. |
| `Meta · token refusé` | Token expiré ou mal copié : régénère-le (étape 3). |
| `tri IA impossible` / `Gemini n'a pas répondu` | Quota gratuit atteint ou modèle renommé. Ajoute une variable GitHub `GEMINI_MODEL` (onglet Variables) avec le nom d'un modèle Flash gratuit listé sur aistudio.google.com. |
| `image pas accessible publiquement` | Le dépôt d'images n'est pas public, ou `IMAGES_REPO` est mal écrit. |
| `git push : … 403` | `IMAGES_TOKEN` expiré ou sans droit *Contents : Read and write*. |

GitHub t'envoie un mail à chaque échec : pas besoin de surveiller.

## Coût

- **Gemini** : version gratuite (environ 2 appels par post).
- **Instagram** : gratuit, limite de 50 posts publiés par l'API sur 24 h (on en fait 6).
- **GitHub** : dépôt privé = 2 000 minutes gratuites par mois. Le bot en consomme environ 1 000 à 1 500. Si tu dépasses un jour, passe le dépôt `cesttombe-bot` en public (minutes illimitées) : tes clés restent cachées dans les Secrets.

## Bon à savoir

- Le bot ne recopie jamais le texte des sources : il réécrit l'info et cite la source sur chaque post.
- Les photos viennent des sources et ne t'appartiennent pas : le crédit est affiché, mais un signalement reste possible.
- `etat.json` garde la trace de ce qui a été vu et publié (le bot le met à jour tout seul). Ne le supprime pas, sinon il pourrait republier une info.
- Tests hors ligne : `python tests/test_local.py`.

Polices : Anton et Space Grotesk, licence SIL Open Font (fichiers `fonts/OFL-*.txt`).
