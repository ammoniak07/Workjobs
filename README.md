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

### Interface graphique (recommandé)

```bash
python -m job_watch.gui
```

Sous Windows, un double-clic sur `run_gui.bat` fait la même chose. L'onglet
**Recherche & sites** permet de saisir le poste recherché, la région, le
type de contrat, d'activer/désactiver Le Forem, Indeed et LinkedIn, et
d'**ajouter vos propres sites** (bouton "Ajouter..." dans "Sites
personnalisés" — voir ci-dessous). L'onglet **Résultats** liste les offres
trouvées ; sélectionnez-en une (ou plusieurs) puis cliquez sur "Préparer un
brouillon" ou "Ignorer".

### Ligne de commande

```bash
python -m job_watch.main
```

(ou `python job_watch/main.py` depuis la racine du dépôt)

Pour chaque nouvelle offre, répondez **o**ui / **n**on / **q**uitter.

Dans les deux cas, la configuration est lue/écrite dans
`job_watch/config.yaml` (copiez `job_watch/config.example.yaml` la première
fois, ou laissez l'interface graphique le faire pour vous). À chaque
exécution, seules les offres pas encore vues sont proposées (le suivi est
stocké dans `job_watch/seen_jobs.json`) — ce suivi est partagé entre
l'interface graphique et la ligne de commande.

### Ajouter un site de recherche d'emploi

En plus de Le Forem, Indeed et LinkedIn (intégrés), vous pouvez ajouter
n'importe quel autre site sans toucher au code : dans l'interface
graphique, "Sites personnalisés" → "Ajouter...", ou directement dans
`config.yaml` sous `sites_personnalises` (voir l'exemple commenté dans
`config.example.yaml`). Il faut fournir :

- l'URL de recherche du site, avec `{mots_cles}` et `{lieu}` à la place du
  poste et de la région (ex : `https://exemple.com/emplois?q={mots_cles}&l={lieu}`),
- les sélecteurs CSS de la page de résultats : le conteneur d'une offre,
  et à l'intérieur le titre, l'entreprise, le lieu et le lien.

Ces sélecteurs s'obtiennent en ouvrant la page de résultats du site dans un
navigateur, clic droit sur une offre → "Inspecter", pour repérer les
classes CSS utilisées.

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
  config.py               # chargement/sauvegarde config + construction des sources
  main.py                  # point d'entrée ligne de commande
  gui.py                    # point d'entrée interface graphique (Tkinter)
  models.py                  # dataclass Job
  store.py                    # suivi des offres déjà traitées (JSON)
  emailer.py                   # génération des brouillons .eml
  templates/
    email_template.txt          # modèle du corps de l'e-mail
  sources/
    base.py                      # interface commune
    leforem.py                    # API Open Data du Forem
    indeed.py                      # scraping HTML
    linkedin.py                     # endpoint public non authentifié
    generic.py                       # site personnalisé piloté par sélecteurs CSS
run_gui.bat              # lance l'interface graphique (Windows, double-clic)
```
