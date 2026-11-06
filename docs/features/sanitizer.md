# Sanitizer — surface de lecture

**TL;DR** : le sanitizer conserve une surface de lecture pour les contenus masqués historiques. Le masquage automatique (`ContentMasker`) et le toggle ont été supprimés le 2026-11-06.

## État actuel

- Les routes `GET /api/mask`, `GET /api/mask/{content_hash}` et `GET /api/sanitizer/stats` restent exposées.
- La table SQLite `masked_content` est conservée pour lire d'éventuelles données existantes.
- Aucun code n'écrit plus dans cette table : le pipeline de masquage automatique a été retiré avec `features/sanitizer/masking.py`.
- Le toggle `POST /api/sanitizer/toggle` n'existe plus.

## Endpoints

| Endpoint | Méthode | Description |
| :--- | :--- | :--- |
| `/api/mask/{content_hash}` | GET | Récupérer un contenu masqué par son hash |
| `/api/mask` | GET | Lister les contenus masqués récents |
| `/api/sanitizer/stats` | GET | Statistiques de la table `masked_content` |

```bash
curl http://localhost:8000/api/mask/abc123def456
curl "http://localhost:8000/api/mask?limit=20"
curl http://localhost:8000/api/sanitizer/stats
```

## Configuration

La section `[sanitizer]` de `config.toml` ne pilote plus qu'un affichage de seuils dans `/api/sanitizer/stats` :

```toml
[sanitizer]
enabled = true
threshold_tokens = 1000
preview_length = 200
```

## Pourquoi cette surface est conservée

Elle permet de consulter des contenus masqués produits par une version antérieure sans casser les scripts qui appellent `/api/mask`. Aucun client actuel du dépôt ne l'utilise pour écrire.

## Golden Rule

**Une route de lecture ne justifie pas de conserver un pipeline d'écriture mort.** Si le masquage automatique revient, il doit être réintroduit comme une feature explicite, avec ses tests et son flag.
