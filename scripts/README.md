# Scripts

This directory is reserved for top-level repository scripts used by development and CI workflows.

Add scripts here when a task needs shared automation that does not belong exclusively to the API or web app.

Current scripts:

- `bootstrap_local_env.sh`
  - creates missing local env files from committed examples without overwriting developer-specific values
