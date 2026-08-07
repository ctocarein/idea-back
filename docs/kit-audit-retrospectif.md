# Kit — Audit rétrospectif d'incohérences

> **Ce qu'on vend :** le repérage des incohérences internes d'un dossier de candidature.
> Pas une note, pas un avis, pas une prédiction de succès. Un constat vérifiable en cinq secondes.
>
> **Pourquoi ça se vend sans confiance préalable :** une erreur de calcul d'un facteur 15 est
> fausse que notre référentiel soit calibré ou non. Le client vérifie lui-même, immédiatement.

État de l'outil au moment d'écrire : **9 contradictions détectées sur 10**, **zéro faux positif**
sur 13 runs cumulés, détection automatique du pays et de la devise, ~3 appels LLM par dossier.

---

## 1. Le message de prise de contact

### Principes

- **On n'offre pas un produit, on offre une trouvaille.** Rien à installer, rien à décider.
- **Rétrospectif = risque nul.** Les dossiers sont déjà traités, aucune décision n'est en jeu,
  et l'anonymisation désamorce la question des données avant qu'elle ne se pose.
- **Un refus doit être aussi informatif qu'un accord.** Si personne ne veut de l'audit, on vient
  d'apprendre — pour le prix d'un e-mail — que le marché n'est pas là.
- **Jamais** les mots « IA », « plateforme », « révolutionnaire », « solution ». On décrit ce
  qu'on trouve, pas comment.

### Version e-mail

> **Objet :** 30 dossiers de votre dernière édition — ce qui vous a échappé
>
> Bonjour [Prénom],
>
> Je travaille sur la détection d'incohérences dans les dossiers de candidature. Pas une
> notation : simplement le repérage de ce qui ne tient pas ensemble à l'intérieur d'un dossier.
> Un chiffre d'affaires incompatible avec le nombre de clients annoncés. Un historique de
> données plus long que l'âge du projet. Une cible qui ne peut pas payer le prix affiché.
>
> Je vous propose quelque chose de simple : donnez-moi **30 dossiers de votre dernière
> édition, anonymisés**. Sous cinq jours, je vous rends la liste des incohérences qu'ils
> contiennent — chacune accompagnée des **deux phrases du dossier qui se contredisent**.
> Vous vérifiez vous-même, en quelques secondes, sans avoir à me croire sur parole.
>
> C'est gratuit et ça ne vous engage à rien : ces dossiers sont déjà traités, aucune décision
> n'est en jeu. Si je ne trouve rien d'utile, dites-le-moi franchement — j'en tirerai la leçon.
>
> La seule chose que je demande en retour, c'est votre retour honnête.
>
> [Signature]

### Version courte (LinkedIn, WhatsApp)

> Bonjour [Prénom], je repère les incohérences internes dans les dossiers de candidature —
> un CA qui ne colle pas au nombre de clients, un historique plus long que l'âge du projet.
> Donnez-moi 30 dossiers déjà traités de votre dernière édition, anonymisés : sous 5 jours je
> vous rends la liste, avec les deux phrases qui se contredisent à chaque fois. Gratuit, sans
> engagement, et si je ne trouve rien d'utile je vous le dirai. Ça vous intéresse de voir ?

### Ce qu'on ne fait jamais dans ce premier contact

- Montrer le Radar, le score, ou quoi que ce soit d'autre que l'audit.
- Demander un rendez-vous avant d'avoir livré quelque chose.
- Promettre un gain de temps chiffré — on ne l'a pas encore mesuré chez eux.

---

## 2. La grille de ciblage

### Les cinq critères

| Critère | Question à se poser | Pourquoi c'est décisif |
|---|---|---|
| **Volume** | Combien de dossiers par an ? | Sous ~100/an, la vérification manuelle reste possible et la douleur est faible. |
| **Enjeu** | Que perd-on sur un mauvais dossier ? | De l'argent perdu (crédit, garantie) fait bien plus mal qu'un mauvais lauréat. |
| **Matière** | Les dossiers contiennent-ils du **texte rédigé** ? | **Prérequis absolu.** Des cases à cocher ne peuvent pas se contredire. |
| **Budget** | Existe-t-il une ligne budgétaire ? | Un incubateur subventionné à court d'argent ne paiera jamais, même convaincu. |
| **Accès** | Peut-on joindre un décideur en un saut ? | Trois intermédiaires = six mois perdus. |

> **La question qualifiante à poser tôt :** *« Vos dossiers contiennent-ils des parties
> rédigées, ou uniquement des champs structurés ? »* Si la réponse est « des cases », on
> remercie et on passe au suivant. Il n'y a rien à contredire dans un formulaire.

### Les cibles, classées

| Cible | Volume | Enjeu | Budget | Accès | Verdict |
|---|---|---|---|---|---|
| **Banque / IMF — dossiers de crédit PME** | élevé | **très fort** *(argent réel)* | fort | moyen | 💰 la plus lucrative |
| **Fonds de garantie** | élevé | **très fort** | fort | moyen | 💰 la plus lucrative |
| **Programme public / bailleur** | élevé | fort *(redevabilité)* | fort | faible | 🎯 la plus stratégique |
| **Concours entrepreneurial** | élevé | moyen | faible | **fort** | 🚪 la meilleure porte d'entrée |
| **Incubateur / accélérateur** | moyen | moyen | moyen | fort | ⚖️ correct |
| **Fondation / ONG** | moyen | moyen | moyen | moyen | ⚖️ correct |
| Incubateur boutique (< 60 dossiers/an) | faible | faible | faible | fort | ❌ éviter |

### La séquence recommandée

1. **Premier audit gratuit → un concours.** Accès facile, volume réel, cycle court. L'objectif
   n'est pas l'argent, c'est **la preuve et le témoignage écrit**.
2. **Deuxième approche → une banque ou un fonds de garantie**, en montrant le résultat du
   premier. Là il y a de l'argent réel en jeu, donc un vrai budget.

> On utilise la cible **accessible** pour fabriquer la preuve, et la cible **lucrative** pour
> encaisser. Ne pas inverser : démarcher une banque sans référence, c'est six mois de silence.

### Signaux d'alerte

- Les dossiers ne sont pas exportables (tout est dans un outil fermé).
- L'interlocuteur veut « en parler à la prochaine réunion du comité » → pas de décideur.
- On vous demande de signer un accord-cadre avant même l'audit gratuit → cycle trop lourd,
  passez au suivant et revenez plus tard.

---

## 3. La trame du rapport d'audit

### Structure

**A. Synthèse (une page)**

- `N` dossiers analysés · `X` présentent au moins une incohérence · **`Y` n'en présentent aucune**
- Répartition des constats par type (arithmétique, temporel, capacité, marché, interne, réglementaire)
- Contexte détecté pour le lot : pays, devise, repère de pouvoir d'achat retenu

**B. Comment lire ce rapport (encadré, une demi-page)**

> Nous constatons, nous ne jugeons pas. Chaque constat cite **deux passages du dossier**
> qui ne peuvent pas être vrais en même temps. Vous vérifiez vous-même.
>
> **L'absence de constat ne signifie pas qu'un dossier est bon** — seulement qu'il est
> cohérent avec lui-même.

**C. Les constats** — un bloc par incohérence

| Champ | Contenu |
|---|---|
| Dossier | référence anonymisée |
| Type | arithmétique · temporel · capacité · marché · interne · réglementaire |
| Gravité | haute · moyenne · basse |
| Passage A | citation exacte |
| Passage B | citation exacte |
| Constat | une phrase factuelle, sans jugement |

**D. Ce que nous n'avons pas cherché** *(section obligatoire)*

- Nous n'évaluons **pas la qualité** du projet, ni ses chances de succès.
- Nous ne vérifions **rien contre des sources externes** : ni registre, ni bilan, ni terrain.
  Une affirmation fausse mais cohérente avec le reste du dossier **ne sera pas détectée**.
- Nous ne détectons que les incohérences **internes au texte fourni**.

**E. Méthode (quelques lignes)**

- Détection automatique du pays et de la devise, pour juger prix et obligations dans le bon contexte.
- Analyse en deux passes complémentaires par dossier.
- **Chaque constat a été relu et validé manuellement avant publication.**

### Les règles de rédaction, non négociables

1. **Aucune note, aucun classement, aucune recommandation.** Dès qu'on note, on redevient
   contestable — et on perd ce qui fait la force du produit.
2. **Toujours dire ce qui n'a pas été trouvé.** La phrase « 273 dossiers sur 300 ne présentent
   aucune incohérence détectée » est ce qui transforme une machine à accuser en audit.
3. **Toujours annoncer les limites** (section D). Ça protège juridiquement et ça installe la
   confiance : un auditeur qui énonce ses angles morts est plus crédible qu'un oracle.
4. **Jamais de constat non relu.** Le filtre humain est la garantie du zéro faux positif —
   c'est-à-dire le produit lui-même. Il ne s'automatise qu'après mesure, et en dernier.

---

## Le premier jalon

Six semaines. Un détecteur mesuré, un rapport livrable, et **au moins un audit rétrospectif
remis à un acteur réel** — payé ou non, mais livré, avec un retour écrit.

Le moment qui décide de tout n'est pas la démo : c'est celui où l'interlocuteur **reconnaît un
dossier qu'il a financé**.
