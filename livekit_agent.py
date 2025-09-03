# livekit_agent.py
import os
import json
from dotenv import load_dotenv

from livekit.agents import (
    AgentSession,
    Agent,
    JobContext,
    WorkerOptions,
    RoomInputOptions,
    cli,
)
from livekit.plugins import openai as lk_openai, elevenlabs, noise_cancellation, silero, langchain as lk_langchain
from livekit.plugins.turn_detector.multilingual import MultilingualModel
from livekit import rtc  # tipos para text streams, room, etc.

from langchain_core.messages import HumanMessage
from langgraph_agent import create_workflow

# ======= Configuración general =======
load_dotenv()

LIVEKIT_URL = os.getenv("LIVEKIT_URL", "ws://localhost:7880")
LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY")
LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")                 # requerido por plugins openai
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")         # requerido por plugin elevenlabs
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "yj30vwTGJxSHezdAGsv9")
ELEVENLABS_MODEL = os.getenv("ELEVENLABS_MODEL", "eleven_flash_v2_5")

# Tópicos de texto (data)
TOPIC_IN = os.getenv("TEXT_TOPIC_IN", "unity")               # Unity -> Agente
TOPIC_OUT = os.getenv("TEXT_TOPIC_OUT", "agent")             # Agente -> Unity

def _require(name: str, value: str | None):
    if not value:
        raise RuntimeError(f"Falta variable de entorno: {name}")
    return value

# ======= Clase del asistente (tono/persona) =======
class Assistant(Agent):
    def __init__(self):
        super().__init__(instructions=(
            "Eres un asistente conversacional breve y claro. "
            "Responde con precisión y sin rodeos."
        ))

# ======= Punto de entrada del worker =======
async def entrypoint(ctx: JobContext):
    """
    1) Conecta al servidor LiveKit (Cloud o local).
    2) Registra un handler de 'Text Streams' para recibir mensajes de Unity (topic=TOPIC_IN).
    3) Arranca una AgentSession con STT+LLM+TTS y 'turn detection'.
    """
    # 1) Conexión al servidor (crea/usa la sala definida por el job)
    await ctx.connect(
        url=_require("LIVEKIT_URL", LIVEKIT_URL),
        api_key=_require("LIVEKIT_API_KEY", LIVEKIT_API_KEY),
        api_secret=_require("LIVEKIT_API_SECRET", LIVEKIT_API_SECRET),
    )
    room = ctx.room  # objeto Room del SDK

    # 2) Prepara el grafo de LangGraph
    workflow = create_workflow()

    # 3) Crea la sesión de voz (audio bidireccional)
    session = AgentSession(
        # Adaptamos LangGraph como "LLM" del pipeline de voz
        llm=lk_langchain.LLMAdapter(graph=workflow),

        # STT: Whisper (OpenAI)
        stt=lk_openai.STT(model="whisper-1", detect_language=True),

        # TTS: ElevenLabs (cámbialo por openai.TTS si prefieres)
        tts=elevenlabs.TTS(model=ELEVENLABS_MODEL, voice_id=ELEVENLABS_VOICE_ID),

        # Detección de turnos + VAD
        turn_detection=MultilingualModel(),
        vad=silero.VAD.load(),

        # Respuestas anticipadas (barge-in)
        preemptive_generation=True,
    )

    # 4) === Manejo de DATA (Text Streams) ===
    #    Unity envía texto al topic TOPIC_IN; respondemos por TOPIC_OUT.
    #    Text Streams es la capa recomendada (auto-chunking, sin límite práctico de tamaño).
    #    https://docs.livekit.io/home/client/data/text-streams/
    async def handle_text_stream(reader: rtc.TextStreamReader, participant_identity: str):
        """
        Lee el stream de texto, ejecuta LangGraph y responde por otro stream.
        """
        # Opción A: acumular todo el texto del stream
        chunks: list[str] = []
        async for chunk in reader:
            chunks.append(chunk)
        incoming_text = "".join(chunks).strip()
        if not incoming_text:
            return

        # Pasar por LangGraph (chat de 1 turno)
        result = workflow.invoke({"messages": [HumanMessage(content=incoming_text)]})
        reply = result["messages"][-1].content

        # Responder como texto (se auto-fragmenta si hace falta)
        await room.local_participant.send_text(
            reply,
            topic=TOPIC_OUT,  # Unity debe escuchar este topic
        )

    # Registrar handler ANTES de iniciar la sesión para no perder eventos
    room.register_text_stream_handler(TOPIC_IN, handle_text_stream)

    # 5) Arrancar la sesión de voz
    await session.start(
        agent=Assistant(),
        room=room,
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVC()
        ),
    )

if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
