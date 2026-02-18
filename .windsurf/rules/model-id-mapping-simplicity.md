---
globs: '["src/kimi_proxy/proxy/router.py"]'
description: S'applique lors du mappage des noms de modèles dans la couche proxy
always_apply: false
---

Conserver le mappage du nom du modèle simple et direct : a) vérifier les correspondances de clé exacte, b) sinon utiliser la logique de split de suffixe. Ne pas implémenter de mappings spécifiques à JetBrains, de retraits de préfixes complexes ou de correspondances floues.