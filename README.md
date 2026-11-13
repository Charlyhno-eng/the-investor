![The Investor — Finance quantitative, décisions éclairées](docs/assets/banner.svg)

# The Investor

The Investor est une application locale d’aide à la décision d’investissement fondée sur la finance quantitative. Elle analyse les données chiffrées des marchés pour étudier les performances, les risques et les tendances, sans intégrer l’analyse macroéconomique ni l’analyse fondamentale traditionnelle des entreprises. **Elle s’utilise sur des entreprises préalablement sélectionnées pour leur solidité et leurs très bons fondamentaux.** Sans cette sélection, les signaux quantitatifs peuvent conduire à de mauvaises décisions : l’application ne permet pas, à elle seule, de juger la qualité d’une entreprise.

## Quick Start

Prérequis : **Python 3.12**, **uv**, **Node.js 22 ou supérieur**, **npm** et **make**. Une connexion Internet est nécessaire pour importer et actualiser les données.

```sh
git clone https://github.com/Charlyhno-eng/the-investor.git
cd the-investor
make install
make import
```

Lancer l’API dans un premier terminal :

```sh
make api
```

Puis l’interface dans un second terminal, depuis le même dossier :

```sh
make web
```

Ouvrir **[http://localhost:5173](http://localhost:5173)**. L’API et sa documentation sont disponibles sur [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs). Ajouter ensuite les actions choisies depuis l’interface ; l’API assure leur import et leur actualisation en arrière-plan.

Les méthodes de calcul, les sources de données et les commandes complémentaires sont détaillées dans la [documentation technique](docs/guide-technique.md).
