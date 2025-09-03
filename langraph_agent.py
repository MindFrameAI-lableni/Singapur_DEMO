from typing import Annotated, TypedDict
from langgraph.graph import START, END, StateGraph
from langgraph.graph.message import add_messages, AnyMessage
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

class State(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]

# Modelo ligero y rápido
MODEL = ChatOpenAI(model="gpt-4o-mini", temperature=0.4)

def chat_node(state: State) -> State:
    """
    Toma el historial en state["messages"] y añade una respuesta del LLM.
    """
    resp = MODEL.invoke(state["messages"])
    return {"messages": [resp]}  # add_messages agregará al historial

def create_workflow():
    g = StateGraph(State)
    g.add_node("chat", chat_node)
    g.add_edge(START, "chat")
    g.add_edge("chat", END)
    return g.compile()

# Prueba local (opcional)
if __name__ == "__main__":
    wf = create_workflow()
    out = wf.invoke({"messages": [HumanMessage(content="Hola, ¿qué tal?")]})
    print(out["messages"][-1].content)
