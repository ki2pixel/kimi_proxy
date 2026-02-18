---
globs: '["src/kimi_proxy/api/router.py"]'
description: S'applique lors de l'édition du routeur principal FastAPI pour garantir une configuration de route propre et standard
always_apply: false
---

Maintenir uniquement des routes API standard (/models, /chat/completions) et supprimer toute route de compatibilité expérimentale spécifique à l'éditeur. Ne pas ajouter de préfixes de compatibilité supplémentaires comme /v1/models ou des routes similaires à Ollama sans examen minutieux.