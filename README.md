# Singapur_DEMO
This repo is for building a (langgraph + livekit + openai) agent demo for the singapur project.

Instala dependencias:

pip install -r requirements.txt


Copia .env.example a .env y rellena claves.

Lanza el worker/agente:

python livekit_agent.py


Conecta tu cliente Unity (o web) a la misma sala y:

Publica audio → el agente te responderá por voz (STT→LangGraph→TTS).

Envía texto por Text Stream con topic=unity → el agente contestará texto por topic=agent.
(En LiveKit Text Streams, usa sendText(...) / streamText(...) del participante local; el SDK se encarga del troceo y entrega. 
LiveKit Docs
)

Consejos / extensiones

Filtrado por tópico: Puedes definir más topics (p. ej. cmd, hud, npc). Cada uno con su propio handler. 
LiveKit Docs

RPC: Si quieres request/response con retorno a un único cliente, registra un RPC method en el agente y llámalo desde Unity (útil para acciones que deben devolver datos). 
LiveKit Docs

Límites de tamaño: con Text Streams no te preocupas (auto-chunking); si usas data packets crudos, recuerda límites y fiabilidad (15–16 KiB máx. por paquete fiable). 
LiveKit Docs

Orden de arranque: conecta (ctx.connect) → registra handlers de texto → session.start(...). 
AssemblyAI