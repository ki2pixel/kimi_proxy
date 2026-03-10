# Kimi Code CLI Skills

This directory contains all the skills for Kimi Code CLI, structured according to the project standards. Each skill is a self-contained unit that can be invoked via specific commands.

## Available Skills

| Skill Name | Description | Usage Command |
|------------|-------------|---------------|
| end | Terminer la session et synchroniser la Memory Bank | `/flow:end` |
| enhance | Améliorer un Prompt avec le Contexte du Projet Kimi Proxy Dashboard | `/flow:enhance` |
| docs-updater | Harmoniser la documentation Kimi Proxy avec analyse statique (cloc, radon, tree) | `/flow:docs-updater` |
| enhance-complex | Planification de tâches complexes avec Shrimp Task Manager | `/flow:enhance-complex` |
| commit-push | Commiter et pusher les modifications vers le dépôt distant | `/flow:commit-push` |
| documentation | Guides de rédaction technique et règles de ponctuation | `/skill:documentation` |

## How to Use

1. Invoke a skill by typing its usage command in the Kimi Code CLI interface.
2. Each skill will provide specific instructions and steps to follow.
3. Ensure all required tools (e.g., `fast_read_file`, `Shell`) are available in the environment.

For detailed usage instructions, see `USAGE.md`.