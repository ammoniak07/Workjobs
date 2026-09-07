# Workjobs

Petit outil en ligne de commande qui :

1. cherche des offres d'emploi sur **Le Forem**, **Indeed** et **LinkedIn**
   selon des critères que vous définissez,
2. pour chaque nouvelle offre (jamais vue lors d'un run précédent), vous
   l'affiche et vous demande **oui / non / quitter**,
3. si vous répondez oui, génère un **brouillon d'e-mail personnalisé**
   (fichier `.eml`, ouvrable dans n'importe quel client mail — Outlook,
   Thunderbird, Mail...) dans `job_watch/drafts/`.

**Aucun e-mail n'est jamais envoyé automatiquement.** L'outil ne fait que
préparer des brouillons ; c'est vous qui les relisez, complétez le
destinataire et le paragraphe de motivation, puis envoyez depuis votre
propre messagerie.

## Installation

```bash
pip install -r job_watch/requirements.txt
cp job_watch/config.example.yaml job_watch/config.yaml
```

Éditez `job_watch/config.yaml` : vos coordonnées, le poste recherché, la
zone géographique, et les sources à activer.

## Utilisation

```bash
python -m job_watch.main
```

(ou `python job_watch/main.py` depuis la racine du dépôt)

À chaque exécution, seules les offres pas encore vues sont proposées (le
suivi est stocké dans `job_watch/seen_jobs.json`).

## Limites importantes à connaître

- **Le Forem** utilise l'API Open Data officielle et publique du Forem
  (https://www.leforem.be/open-data.html) : c'est la source la plus
  fiable et la seule totalement autorisée par les conditions d'utilisation
  du site.
- **Indeed** ne propose plus d'API publique : la source scrape les pages
  de résultats HTML. Indeed protège ces pages (Cloudflare, pages de
  vérification) et peut bloquer ou renvoyer 0 résultat sans préavis. Si
  ça arrive, les sélecteurs CSS dans `job_watch/sources/indeed.py` doivent
  probablement être ajustés à la nouvelle mise en page du site.
- **LinkedIn** interdit explicitement le scraping dans ses conditions
  d'utilisation. Cette source utilise un point d'accès HTML public non
  documenté officiellement (celui utilisé par le bouton "Voir plus
  d'offres" du site, sans connexion donc sans risque pour un compte
  LinkedIn) mais peut cesser de fonctionner à tout moment. Utilisez cette
  source avec modération (pas d'exécutions en boucle rapprochée) et à vos
  propres risques.
- Les offres scrapées **n'exposent en général pas d'adresse e-mail directe
  du recruteur** : le champ "À" des brouillons `.eml` est donc laissé
  vide. Il faut retrouver l'adresse à contacter via le lien de l'offre, ou
  utiliser le formulaire de candidature du site en copiant le texte
  généré.
- Le paragraphe central du brouillon (expérience/motivation) est un
  espace réservé à personnaliser vous-même — ce n'est pas un générateur
  de contenu automatique.

## Structure

```
job_watch/
  config.example.yaml   # modèle de configuration à copier
  main.py                # point d'entrée
  models.py               # dataclass Job
  store.py                 # suivi des offres déjà traitées (JSON)
  emailer.py               # génération des brouillons .eml
  templates/
    email_template.txt     # modèle du corps de l'e-mail
  sources/
    base.py                 # interface commune
    leforem.py               # API Open Data du Forem
    indeed.py                 # scraping HTML
    linkedin.py                # endpoint public non authentifié
```
