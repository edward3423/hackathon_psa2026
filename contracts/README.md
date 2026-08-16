# Shared contracts

Pydantic models in `src/cascade/contracts.py` are the authoritative contracts.
`contracts/openapi.json` and `frontend/src/api/schema.d.ts` are generated files.

Regenerate both with:

```powershell
npm run generate:types
```

Do not edit generated TypeScript API types manually.

