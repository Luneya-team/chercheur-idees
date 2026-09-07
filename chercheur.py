#!/usr/bin/env python3
"""
Chercheur d'idees - tourne sur GitHub Actions, machine eteinte.
Collecte des faits chiffres, en tire des idees, applique les questions du filtre,
s'arrete au premier OUI. Tout est ecrit dans base.json et resultats.md.
"""
import json, os, re, sys, time, urllib.request, random
from datetime import datetime, timezone

CLE      = os.environ.get("OPENROUTER_KEY", "")
MODELE   = os.environ.get("MODELE", "openrouter/free")
TOURS    = int(os.environ.get("TOURS", "3"))
PAR_TOUR = int(os.environ.get("PAR_TOUR", "4"))
URL      = "https://openrouter.ai/api/v1/chat/completions"
BASE     = "base.json"
SORTIE   = "resultats.md"
PAUSE    = 3.5          # 20 requetes par minute en gratuit

SYSTEME = ("Tu reponds UNIQUEMENT par du JSON valide. Aucune explication, aucun "
           "raisonnement visible, aucun texte avant ou apres, aucun bloc de code. "
           "Ta reponse commence par [ ou { et se termine par ] ou }.")

def charger():
    if os.path.exists(BASE):
        try:
            return json.load(open(BASE, encoding="utf-8"))
        except Exception:
            pass
    return {"faits": [], "idees": [], "cimetiere": {}, "terrains": []}

def sauver(b):
    json.dump(b, open(BASE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

def dire(m):
    print(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] {m}", flush=True)

_dernier = [0.0]
def appel(prompt, essais=3):
    for n in range(1, essais + 1):
        ecart = time.time() - _dernier[0]
        if ecart < PAUSE:
            time.sleep(PAUSE - ecart)
        _dernier[0] = time.time()
        corps = json.dumps({
            "model": MODELE,
            "messages": [{"role": "system", "content": SYSTEME},
                         {"role": "user", "content": prompt}],
            "max_tokens": 2000,
            "temperature": 0.8,
            "reasoning": {"exclude": True},
        }).encode()
        req = urllib.request.Request(URL, data=corps, headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + CLE,
            "HTTP-Referer": "https://github.com/Luneya-team",
            "X-Title": "Chercheur d'idees",
        })
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                d = json.loads(r.read())
        except Exception as e:
            dire(f"  appel echoue ({n}/{essais}) : {e}")
            time.sleep(5)
            continue
        if "error" in d:
            msg = d["error"].get("message", "")
            dire(f"  refus ({n}/{essais}) : {msg[:140]}")
            if "rate" in msg.lower() or "429" in msg:
                time.sleep(60)
            continue
        m = (d.get("choices") or [{}])[0].get("message", {}) or {}
        txt = m.get("content") or m.get("reasoning") or m.get("reasoning_content") or ""
        if isinstance(txt, list):
            txt = "\n".join(b.get("text", "") for b in txt)
        if txt.strip():
            dire(f"  recu {len(txt)} car.")
            return txt
        dire(f"  reponse vide ({n}/{essais})")
    raise RuntimeError("aucune reponse exploitable")

def lire_json(t):
    c = re.sub(r"```json|```", "", t).strip()
    pos = [i for i in (c.find("["), c.find("{")) if i >= 0]
    if pos:
        c = c[min(pos):]
    try:
        return json.loads(c)
    except Exception:
        pass
    out = []
    for m in re.finditer(r"\{[^{}]*\}", c):
        try:
            out.append(json.loads(m.group(0)))
        except Exception:
            pass
    if out:
        return out
    raise ValueError("JSON illisible")

def est_oui(v):
    return str(v or "").strip().lower().startswith(("oui", "yes", "true"))

# ---------------------------------------------------------------- etapes

def collecter():
    p = """Trouve 6 faits reels pour alimenter une recherche d'idees de produit logiciel.

3 missions payees publiees pour des taches repetitives et mecaniques : rapprocher deux tableurs,
recopier des donnees d'un outil vers un autre, preparer un fichier d'import, remplir un modele a
chaque livraison. Note la tache, le tarif affiche, la frequence.

3 plaintes recurrentes d'utilisateurs dans les avis 1 et 2 etoiles d'outils etablis, ou dans des
fils de support restes sans reponse. Note le manque exact et le produit concerne.

Rejette les pages ecrites par des editeurs pour vendre : listes d'outils, "les 15 meilleurs".
Il te faut de la parole primaire. Chaque fait doit porter un chiffre : tarif, nombre, frequence.

JSON compact :
[{"fait":"20 mots max","chiffre":"le tarif ou le nombre","source":"produit ou plateforme"}]"""
    return lire_json(appel(p))

def fabriquer(faits, n, base):
    morts = ", ".join(f"Q{q}: {c}" for q, c in base["cimetiere"].items())
    terr = " | ".join(base["terrains"][-8:])
    p = f"""Tu transformes des faits reels en idees de produit logiciel pour un developpeur seul,
un mois de developpement maximum, marche mondial en anglais.

Faits :
""" + "\n".join(f"{i+1}. {f.get('fait','')} — {f.get('chiffre','')} — {f.get('source','')}"
                for i, f in enumerate(faits)) + f"""

{"Terrains deja brules, n'y retourne pas : " + terr if terr else ""}
{"Historique des morts par question : " + morts if morts else ""}

Regles strictes :
- Pas de reecriture allegee, locale ou plus rapide d'un logiciel existant.
- Une seule idee au maximum dont la sortie est un rapport de verification.
- Le prix vient du tarif observe dans le fait, jamais invente.
- Ecris le moment precis ou le produit intervient, pas le domaine.

Produis {n} idees. JSON compact :
[{{"nom":"3 mots","moment":"15 mots","produit":"20 mots","prix":"tire du fait","source":"le fait"}}]"""
    return lire_json(appel(p))

def juger(idee):
    p = f"""Tu juges une idee avec trois questions. Un seul NON la tue.

Idee : {idee.get('nom')}
Moment : {idee.get('moment')}
Produit : {idee.get('produit')}

Q1 DECLENCHEUR — La situation elle-meme amene-t-elle a l'utiliser, sans que l'utilisateur ait a
etre convaincu qu'il a un probleme ? Le moment doit porter exactement l'intention de l'action.
Q2 FREQUENCE — Le meme utilisateur s'en sert-il au moins une fois par mois, toute l'annee ?
Q3 PREMIER USAGE — Est-ce utile des la premiere minute, sans donnees accumulees ?

Ne tue pas par prudence : un motif que tu ne peux pas justifier concretement ne s'applique pas.

JSON sur une ligne, sans texte autour :
{{"verdict":"OUI","q":0,"pourquoi":"15 mots max"}}
verdict vaut exactement OUI ou NON. Si NON, q contient 1, 2 ou 3. Un NON avec q a 0 est interdit."""
    return lire_json(appel(p))

def verifier(idee):
    p = f"""Tu verifies une idee de produit.

Idee : {idee.get('nom')}
Moment : {idee.get('moment')}
Produit : {idee.get('produit')}

Q4 FAISABILITE ET FIABILITE — L'acces aux donnees est-il reellement possible ET le resultat
fiable ? Pour repondre NON, nomme ce qui rend le resultat non fiable : quels elements manquent,
d'ou ils viennent, pourquoi ils ne peuvent pas etre reproduits.
Q5 CONCURRENT GRATUIT — L'utilisateur obtient-il 80 % du resultat gratuitement sans rien
installer ? Pour repondre NON, ecris le geste gratuit exact, etape par etape, et son temps.
Sans ces etapes, cette question ne s'applique pas.
Q6 CONCURRENTS — Nomme-les. Interviennent-ils au meme moment avec le meme resultat ? Un
concurrent qui intervient a un autre moment n'est pas un NON.

Ne tue pas par prudence. Sans preuve, une question ne s'applique pas.

JSON sur une ligne :
{{"verdict":"OUI","q":0,"pourquoi":"20 mots max","preuves":["nom - detail"]}}
Si NON, q contient 4, 5 ou 6. Un NON avec q a 0 est interdit."""
    return lire_json(appel(p))

# ---------------------------------------------------------------- rapport

def ecrire_rapport(base, gagnante):
    L = ["# Chercheur d'idees",
         "",
         f"Derniere execution : {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
         "",
         f"- faits en base : {len(base['faits'])}",
         f"- idees jugees : {len(base['idees'])}",
         f"- OUI : {sum(1 for i in base['idees'] if i.get('verdict') == 'OUI')}",
         ""]
    if gagnante:
        L += ["## OUI — " + gagnante.get("nom", ""), "",
              f"**Moment** : {gagnante.get('moment','')}", "",
              f"**Produit** : {gagnante.get('produit','')}", "",
              f"**Prix envisage** : {gagnante.get('prix','')}", "",
              gagnante.get("pourquoi", ""), "",
              "> A repasser a la main dans le filtre complet avant d'ecrire du code. "
              "La question 7, le test a moins de 100 euros, n'a pas ete traitee ici.", ""]
    if base["cimetiere"]:
        L += ["## Ou ca meurt", ""]
        for q, n in sorted(base["cimetiere"].items(), key=lambda x: -x[1]):
            L.append(f"- Question {q} : {n} idee(s)")
        L.append("")
    L += ["## Idees jugees", ""]
    for i in reversed(base["idees"][-40:]):
        v = i.get("verdict")
        etiq = "OUI" if v == "OUI" else ("EN ATTENTE" if v == "ATTENTE" else f"NON Q{i.get('q')}")
        L.append(f"- **{i.get('nom','')}** — `{etiq}` — {i.get('moment','')} — {i.get('pourquoi','')}")
    L += ["", "## Faits en base", ""]
    for f in base["faits"][-30:]:
        L.append(f"- {f.get('fait','')} — {f.get('chiffre','')} — {f.get('source','')}")
    open(SORTIE, "w", encoding="utf-8").write("\n".join(L))

# ---------------------------------------------------------------- boucle

def main():
    if not CLE:
        dire("OPENROUTER_KEY absente"); sys.exit(1)
    base = charger()
    dire(f"base : {len(base['faits'])} faits, {len(base['idees'])} idees deja jugees")
    gagnante = None

    for t in range(1, TOURS + 1):
        if len(base["faits"]) < 6:
            dire(f"tour {t} — collecte")
            try:
                f = collecter()
                base["faits"] += f
                sauver(base)
                dire(f"  {len(f)} faits collectes (base : {len(base['faits'])})")
            except Exception as e:
                dire(f"  collecte echouee : {e}")
                if not base["faits"]:
                    continue
        else:
            dire(f"tour {t} — faits reutilises ({len(base['faits'])}), aucune recherche")

        lot = random.sample(base["faits"], min(6, len(base["faits"])))
        dire(f"tour {t} — fabrication")
        try:
            idees = fabriquer(lot, PAR_TOUR, base)
        except Exception as e:
            dire(f"  fabrication echouee : {e}")
            continue

        for idee in idees:
            nom = idee.get("nom", "sans nom")
            dire(f"  {nom} — questions 1 a 3")
            try:
                v = juger(idee)
            except Exception as e:
                dire(f"    jugement illisible : {e}")
                continue
            q = int(v.get("q") or 0)
            if not est_oui(v.get("verdict")) and q >= 1:
                base["cimetiere"][str(q)] = base["cimetiere"].get(str(q), 0) + 1
                base["idees"].append({**idee, "verdict": "NON", "q": q,
                                      "pourquoi": v.get("pourquoi", "")})
                sauver(base)
                dire(f"    MORT en Q{q} : {v.get('pourquoi','')[:90]}")
                continue

            dire(f"    passe — verification 4 a 6")
            try:
                w = verifier(idee)
            except Exception as e:
                dire(f"    verification illisible : {e}")
                continue
            q2 = int(w.get("q") or 0)
            if est_oui(w.get("verdict")):
                idee["pourquoi"] = w.get("pourquoi", "")
                idee["preuves"] = w.get("preuves", [])
                base["idees"].append({**idee, "verdict": "OUI"})
                sauver(base)
                gagnante = idee
                dire(f"    OUI — {nom}")
                break
            if q2 >= 4:
                base["cimetiere"][str(q2)] = base["cimetiere"].get(str(q2), 0) + 1
                base["idees"].append({**idee, "verdict": "NON", "q": q2,
                                      "pourquoi": w.get("pourquoi", "")})
                terrain = " ".join(idee.get("produit", "").split()[:4])
                if terrain and terrain not in base["terrains"]:
                    base["terrains"].append(terrain)
                dire(f"    MORT en Q{q2} : {w.get('pourquoi','')[:90]}")
            else:
                base["idees"].append({**idee, "verdict": "ATTENTE", "q": 0,
                                      "pourquoi": w.get("pourquoi", "")})
                dire(f"    en attente — verification non concluante")
            sauver(base)
        if gagnante:
            break

    sauver(base)
    ecrire_rapport(base, gagnante)
    dire("OUI trouve, arret." if gagnante else "aucun OUI cette fois, base conservee.")

if __name__ == "__main__":
    main()
