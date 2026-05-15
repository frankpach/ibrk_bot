# Module Registry: refactor

**Module**: refactor
**Last Updated**: 2026-05-14

## This Module

**Name**: refactor (arch-refactor)
**Path**: app/ (refactor transversal a todo el codebase)
**Status**: in_development

## Related Modules

| Module | Enabled | Relationship to this module |
|--------|---------|----------------------------|
| app/db/database.py | yes | Monolito a dividir — core del refactor |
| app/api/main.py | yes | Routes a separar en 6 archivos |
| app/llm/loop.py | yes | HTTP interno a eliminar |
| app/positions/manager.py | yes | HTTP interno a eliminar |
| app/system/controller.py | yes | Reemplazar con PersistedSystemState |
| run.py | yes | Slim down a ~50 LOC |
