# Interfaz de la plataforma (Angular)

Diseño: `docs/diseno-web.md`. Angular 21.2.25 con Node 20.19 o superior; versiones exactas en `package-lock.json`.

Desde esta carpeta, con la API en marcha en 127.0.0.1:5000 (ver `docs/diseno-web.md` §4):

```
npm ci        # la primera vez
npm start     # http://localhost:4200, con /api redirigido a la API (proxy.conf.json)
npm test      # pruebas unitarias (Vitest)
npm run build
```

En el equipo del autor, `node_modules` es un enlace de directorio (junction) a una carpeta fuera de OneDrive. `npm ci` y
`npm install` lo sustituyen por una carpeta real: después hay que volver a moverla y enlazarla.
