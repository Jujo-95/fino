# Fino y su equipo

- La UI de conversaciones usa exclusivamente `v2-finops-report-orchestrator`, visible como **Fino**. Las conversaciones históricas de otros agentes se conservan en almacenamiento; no se borran ni se fusionan con Fino.
- El equipo se presenta en lista. Solo Fino permite crear conversaciones. Elegir un especialista abre su ficha, función, capacidades y casos de uso públicos. «Pedir ayuda a Fino» rellena el borrador del chat; no lo envía automáticamente.
- Las consultas a especialistas reutilizan la delegación interna existente de LangGraph. El prompt aclara la identidad de Fino, la selección de especialistas relevantes y la obligación de esperar una contribución real.
- Los separadores permiten arrastrar el listado y el hilo; el chat principal ocupa el ancho restante. Flechas ajustan 24 px; Home/End usan límites; doble clic restablece el ancho inicial. Las preferencias se guardan localmente. En pantallas pequeñas se conserva el hilo superpuesto existente.
- La navegación permite contraerse a iconos, con etiquetas accesibles y títulos. La preferencia persiste entre recargas.
- Modo de producto predeterminado: un cliente, sin selector ni creación de clientes en la navegación. Para instalaciones que lo requieren, compilar con `VITE_ENABLE_MULTI_CLIENT=true`. `VITE_CLIENT_ID` fija explícitamente el cliente de una instalación; si no existe, se muestra un error y no se cambia silenciosamente a otro.
- Estas opciones de frontend controlan presentación y selección. Los controles de autenticación y autorización del despliegue deben seguir imponiendo su alcance de cliente en backend.
- Validación: TypeScript y build Vite, sin navegador ni llamadas a modelos. No se añadieron dependencias ni servicios.
