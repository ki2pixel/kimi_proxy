---
name: end
description: Terminer la Session et Synchroniser la Memory Bank
alwaysApply: false
---

### `/end` — Terminer la session et synchroniser la Memory Bank
1. **Charger le contexte**  
   - Use the 'mcp0_fast_read_file' tool to read ONLY 'activeContext.md' and 'progress.md' for session summarization. ALWAYS use 'memory-bank' as the `projectName` parameter.
   - Do NOT read productContext.md, systemPatterns.md or decisionLog.md unless a major architectural decision was made during the session.
   - If older decisions need to be reviewed, use targeted search instead of loading entire files.
2. **Exécuter `UMB` conformément aux règles**  
   - Suspendre la tâche en cours puis résumer la session.  
   - Utiliser `search` pour identifier les fichiers additionnels à consulter (ex. docs liés à la session).
3. **Mettre à jour la Memory Bank**  
   - Update the files using the 'mcp0_fast_edit_block' tool.
   - Before each modification, read the relevant section with 'mcp0_fast_read_file' to minimize changes.
   - Document decisions, progress and active context according to the protocol.
4. **Clôturer la session**  
   - Résumer les tâches finalisées dans la réponse utilisateur.  
   - Vérifier avec 'mcp0_fast_read_file' que `progress.md` indique "Aucune tâche active" et que `activeContext.md` est revenu à l'état neutre.

**Locking Instruction:** Utilisez les outils fast-filesystem (mcp0_fast_*) pour accéder aux fichiers memory-bank avec des chemins absolus.